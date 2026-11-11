"""Sleeper D3: the current-season experience on the mixed-era fixture.

The 2026 fixture season has weeks 1-8 finalized and week 9 unfinished (``finalized=false``, live
scores). The user's rule: the unfinished week is unscored and counts nowhere until the weekly
capture resolves it (``docs/sleeper/00`` §3). Variants (week 9 finalized, idle postseason rows, a
huge live score) are test-only writes to temp copies; ``src/`` stays read-only.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine
from tests.sleeper_fixture import SLEEPER_YEAR
from tests.test_d2_source_neutral_points import scored_mixed_db  # noqa: F401 (fixture)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

PENDING_WEEK = 9


def _data(c: TestClient, url: str) -> Any:
    r = c.get(url)
    assert r.status_code == 200, (url, r.text)
    return r.json()["data"]


def _copy(src: Path, out: Path, mutate: Callable[[sqlite3.Connection], None] | None) -> Path:
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(out)
    try:
        s.backup(d)
        if mutate is not None:
            mutate(d)
            d.commit()
    finally:
        d.close()
        s.close()
    return out


def _client_for(path: Path) -> Iterator[TestClient]:
    eng = create_readonly_engine(f"sqlite:///{path}")
    with TestClient(create_app(eng, cache=AnalyticsCache(), cors_origins=[])) as c:
        yield c
    eng.dispose()


def _sid(db: Path) -> int:
    return int(_rows(db, "SELECT season_id FROM seasons WHERE year=?", SLEEPER_YEAR)[0][0])


def _rows(db: Path, sql: str, *args: Any) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return list(con.execute(sql, args))
    finally:
        con.close()


# ── mutations for temp copies ───────────────────────────────────────────────


def _finalize_week9(con: sqlite3.Connection) -> None:
    """What the weekly capture does once week 9 resolves."""
    for mid, ts, os_, extra in list(
        con.execute(
            "SELECT m.matchup_id, m.team_score, m.opponent_score, m.extra_data FROM matchups m "
            "JOIN seasons s ON s.season_id=m.season_id WHERE s.year=? AND m.week=?",
            (SLEEPER_YEAR, PENDING_WEEK),
        )
    ):
        e = json.loads(extra)
        e["finalized"] = True
        is_win = None if ts == os_ else int(ts > os_)
        con.execute(
            "UPDATE matchups SET is_win=?, extra_data=? WHERE matchup_id=?",
            (is_win, json.dumps(e), mid),
        )


def _huge_live_score(con: sqlite3.Connection) -> None:
    """A week-9 live score and a week-9 player score far above every record."""
    mid = con.execute(
        "SELECT m.matchup_id FROM matchups m JOIN seasons s ON s.season_id=m.season_id "
        "WHERE s.year=? AND m.week=? ORDER BY m.matchup_id LIMIT 1",
        (SLEEPER_YEAR, PENDING_WEEK),
    ).fetchone()[0]
    con.execute("UPDATE matchups SET team_score=999.0 WHERE matchup_id=?", (mid,))
    rid, extra = con.execute(
        "SELECT roster_id, extra_data FROM team_rosters WHERE season_year=? AND week=? "
        "AND is_starter=1 LIMIT 1",
        (SLEEPER_YEAR, PENDING_WEEK),
    ).fetchone()
    e = json.loads(extra)
    e["platform_points"] = 500.0
    con.execute("UPDATE team_rosters SET extra_data=? WHERE roster_id=?", (json.dumps(e), rid))


def _idle_postseason(con: sqlite3.Connection) -> None:
    """Two week-15 byes, as Sleeper loads them: a real score, no opponent."""
    sid = con.execute("SELECT season_id FROM seasons WHERE year=?", (SLEEPER_YEAR,)).fetchone()[0]
    teams = [
        r[0] for r in con.execute("SELECT team_id FROM teams WHERE season_id=? LIMIT 2", (sid,))
    ]
    cols = [r[1] for r in con.execute("PRAGMA table_info(matchups)")]
    template = dict(
        zip(
            cols,
            con.execute("SELECT * FROM matchups WHERE season_id=? LIMIT 1", (sid,)).fetchone(),
            strict=True,
        )
    )
    for tid in teams:
        row = {
            **template,
            "matchup_id": None,
            "team_id": tid,
            "week": 15,
            "opponent_team_id": None,
            "opponent_score": None,
            "team_score": 321.0,
            "is_win": None,
            "is_playoff": 0,
            "extra_data": json.dumps({"finalized": True, "postseason_role": "bye"}),
        }
        keys = [k for k in cols if k != "matchup_id"]
        con.execute(
            f"INSERT INTO matchups ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
            [row[k] for k in keys],
        )


@pytest.fixture(scope="module")
def variant(
    mixed_era_db_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> Callable[[Callable[[sqlite3.Connection], None]], Path]:
    def make(mutate: Callable[[sqlite3.Connection], None]) -> Path:
        out = tmp_path_factory.mktemp("dzd3") / "fantasy.db"
        return _copy(mixed_era_db_path, out, mutate)

    return make


# ── standings ───────────────────────────────────────────────────────────────


def _hand_standings(db: Path) -> dict[int, tuple[int, int, int, float, float]]:
    """W-L-T / PF / PA per team from finalized regular-season games, summed by hand."""
    out: dict[int, list[float]] = {}
    for tid, ts, os_, is_win in _rows(
        db,
        "SELECT m.team_id, m.team_score, m.opponent_score, m.is_win FROM matchups m "
        "JOIN seasons s ON s.season_id=m.season_id WHERE s.year=? AND m.week<=14 "
        "AND m.opponent_team_id IS NOT NULL "
        "AND json_extract(m.extra_data,'$.finalized')=1",
        SLEEPER_YEAR,
    ):
        a = out.setdefault(tid, [0, 0, 0, 0.0, 0.0])
        idx = 0 if is_win == 1 else 1 if is_win == 0 else 2
        a[idx] += 1
        a[3] += ts
        a[4] += os_
    return {
        t: (int(a[0]), int(a[1]), int(a[2]), round(a[3], 2), round(a[4], 2)) for t, a in out.items()
    }


def test_standings_count_finalized_weeks_only(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    sid = _sid(mixed_era_db_path)
    body = _data(mixed_client, f"/v1/seasons/{sid}/standings")
    assert body["through_week"] == PENDING_WEEK - 1
    assert body["pending_week"] == PENDING_WEEK
    assert body["rank_basis"] == "computed"
    hand = _hand_standings(mixed_era_db_path)
    for r in body["rows"]:
        w, lo, t, pf, pa = hand[r["team_id"]]
        assert (r["wins"], r["losses"], r["ties"]) == (w, lo, t)
        assert r["ties"] == 0  # week 9's live scores are not a tie
        assert r["points_for"] == pytest.approx(pf, abs=0.01)
        assert r["points_against"] == pytest.approx(pa, abs=0.01)
        assert r["streak"]["result"] in {"W", "L"}
        assert w + lo + t == PENDING_WEEK - 1


def test_timeline_and_insights_stop_at_last_finalized(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    sid = _sid(mixed_era_db_path)
    tl = _data(mixed_client, f"/v1/seasons/{sid}/standings/timeline")
    assert {max(p["week"] for p in t["points"]) for t in tl["teams"]} == {PENDING_WEEK - 1}
    ins = _data(mixed_client, f"/v1/seasons/{sid}/standings/insights")
    assert ins["through_week"] == PENDING_WEEK - 1


# ── week matchups / box score ───────────────────────────────────────────────


def test_pending_week_lists_unscored_pairings(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    sid = _sid(mixed_era_db_path)
    wk = _data(mixed_client, f"/v1/seasons/{sid}/weeks/{PENDING_WEEK}/matchups")
    assert wk["pending"] is True
    assert len(wk["games"]) == 6
    for g in wk["games"]:
        assert g["pending"] is True
        assert g["winner_team_id"] is None and g["margin"] is None and g["flags"] == []
        for side in (g["team_a"], g["team_b"]):
            assert side["score"] is None and side["is_winner"] is False
    done = _data(mixed_client, f"/v1/seasons/{sid}/weeks/8/matchups")
    assert done["pending"] is False
    assert all(not g["pending"] and g["team_a"]["score"] is not None for g in done["games"])


def test_pending_box_score_is_a_gap(mixed_client: TestClient, mixed_era_db_path: Path) -> None:
    (mid,) = _rows(
        mixed_era_db_path,
        "SELECT m.matchup_id FROM matchups m JOIN seasons s ON s.season_id=m.season_id "
        "WHERE s.year=? AND m.week=? LIMIT 1",
        SLEEPER_YEAR,
        PENDING_WEEK,
    )[0]
    body = _data(mixed_client, f"/v1/matchups/{mid}/box-score")
    assert body["available"] is False
    assert body["reason"] == "week_pending"
    assert body.get("home") is None and body.get("winner_team_id") is None
    assert body["official_points_source"] == "sleeper"


def test_box_score_commissioner_override_and_source(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    (mid,) = _rows(
        mixed_era_db_path,
        "SELECT m.matchup_id FROM matchups m JOIN seasons s ON s.season_id=m.season_id "
        "WHERE s.year=? AND json_extract(m.extra_data,'$.custom_points') IS NOT NULL",
        SLEEPER_YEAR,
    )[0]
    body = _data(mixed_client, f"/v1/matchups/{mid}/box-score")
    assert body["commissioner_override"] == {"official": 112.46, "custom": 117.46}
    assert body["official_points_source"] == "sleeper"


def test_sleeper_box_score_mirrors_legacy_structure(scored_mixed_db: Path) -> None:  # noqa: F811
    legacy_mid, sleeper_mid = (
        _rows(
            scored_mixed_db,
            "SELECT m.matchup_id FROM matchups m JOIN seasons s ON s.season_id=m.season_id "
            f"WHERE s.year {op} ? AND m.opponent_team_id IS NOT NULL "
            "AND s.year IN (SELECT DISTINCT ss.year FROM seasons ss JOIN player_stats_scored p "
            "ON p.season_id=ss.season_id) ORDER BY m.week, m.matchup_id LIMIT 1",
            SLEEPER_YEAR,
        )[0][0]
        for op in ("<", "=")
    )
    for c in _client_for(scored_mixed_db):
        legacy = _data(c, f"/v1/matchups/{legacy_mid}/box-score")
        sleeper = _data(c, f"/v1/matchups/{sleeper_mid}/box-score")
    assert legacy["available"] is True and sleeper["available"] is True
    assert set(sleeper) == set(legacy)
    assert set(sleeper["home"]) == set(legacy["home"])
    assert set(sleeper["home"]["lineup"][0]) == set(legacy["home"]["lineup"][0])
    assert legacy["official_points_source"] == "nfl_com"
    assert legacy["commissioner_override"] is None


def test_bench_or_reserve_rows_carry_a_slot_note(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    (tid,) = _rows(
        mixed_era_db_path,
        "SELECT team_id FROM team_rosters WHERE season_year=? AND week=1 "
        "AND json_extract(extra_data,'$.slot_certainty')='bench_or_reserve' LIMIT 1",
        SLEEPER_YEAR,
    )[0]
    body = _data(mixed_client, f"/v1/teams/{tid}/roster?week=1")
    notes = {p["slot_note"] for p in body["players"] if p["roster_slot"] == "BN"}
    assert notes == {"bench_or_reserve"}


def test_pending_week_team_roster_shows_no_live_points(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    (tid,) = _rows(
        mixed_era_db_path,
        "SELECT t.team_id FROM teams t JOIN seasons s ON s.season_id=t.season_id WHERE s.year=? LIMIT 1",
        SLEEPER_YEAR,
    )[0]
    body = _data(mixed_client, f"/v1/teams/{tid}/roster?week={PENDING_WEEK}")
    assert body["week_pending"] is True
    assert body["players"] and all(p["league_points"] is None for p in body["players"])


# ── team schedule / transactions ────────────────────────────────────────────


def test_team_schedule_pending_week_has_no_result(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    (tid,) = _rows(
        mixed_era_db_path,
        "SELECT t.team_id FROM teams t JOIN seasons s ON s.season_id=t.season_id WHERE s.year=? LIMIT 1",
        SLEEPER_YEAR,
    )[0]
    games = _data(mixed_client, f"/v1/teams/{tid}/schedule")["games"]
    wk9 = next(g for g in games if g["week"] == PENDING_WEEK)
    assert wk9["pending"] is True
    assert wk9["result"] is None and wk9["team_score"] is None and wk9["margin"] is None
    assert all(g["result"] in {"W", "L", "T"} for g in games if g["week"] < PENDING_WEEK)
    trend = _data(mixed_client, f"/v1/teams/{tid}/scoring-trend")["points"]
    assert max(p["week"] for p in trend) == PENDING_WEEK - 1


def test_team_transactions_drop_failed_claims_and_show_asset_legs(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    failed = {
        r[0]
        for r in _rows(
            mixed_era_db_path,
            "SELECT transaction_id FROM transactions t JOIN seasons s ON s.season_id=t.season_id "
            "WHERE s.year=? AND t.status='failed'",
            SLEEPER_YEAR,
        )
    }
    assert failed
    asset_legs = _rows(
        mixed_era_db_path,
        "SELECT t.team_id FROM transactions t JOIN seasons s ON s.season_id=t.season_id "
        "WHERE s.year=? AND t.transaction_type='trade' AND t.player_id IS NULL",
        SLEEPER_YEAR,
    )
    team_ids = {
        r[0]
        for r in _rows(
            mixed_era_db_path,
            "SELECT t.team_id FROM teams t JOIN seasons s ON s.season_id=t.season_id WHERE s.year=?",
            SLEEPER_YEAR,
        )
    }
    asset_teams = {tid for (tid,) in asset_legs}
    for tid in team_ids:
        items = _data(mixed_client, f"/v1/teams/{tid}/transactions")["transactions"]
        assert not {t["transaction_id"] for t in items} & failed
        legs = [t for t in items if t["trade_assets"] is not None]
        assert len(legs) == (1 if tid in asset_teams else 0)
        for leg in legs:
            assert leg["player_id"] is None
            assert leg["trade_assets"]["picks_in"] or leg["trade_assets"]["picks_out"]


# ── records / head-to-head ──────────────────────────────────────────────────


def test_records_label_in_progress_season(mixed_client: TestClient) -> None:
    book = _data(mixed_client, "/v1/records")
    for key in ("highest_team_score", "biggest_blowout", "best_player_week"):
        rec = book[key]
        if rec.get("season_year") == SLEEPER_YEAR:
            assert rec["through_week"] == PENDING_WEEK - 1
            assert rec["week"] < PENDING_WEEK
        else:
            assert rec.get("through_week") is None
    # a partial season never sets a season-total record
    assert book["worst_season_points_for"]["season_year"] != SLEEPER_YEAR


def test_unfinished_week_never_sets_a_record(variant: Any) -> None:
    db = variant(_huge_live_score)
    for c in _client_for(db):
        book = _data(c, "/v1/records")
        sid = _sid(db)
        st = _data(c, f"/v1/seasons/{sid}/standings")
    assert book["highest_team_score"]["value"] < 999.0
    assert book["highest_scoring_matchup"]["value"] < 999.0
    assert book["best_player_week"]["value"] < 500.0
    hand = _hand_standings(db)
    assert all(
        r["points_for"] == pytest.approx(hand[r["team_id"]][3], abs=0.01) for r in st["rows"]
    )


def test_finalizing_the_week_adds_it_everywhere(variant: Any) -> None:
    db = variant(_finalize_week9)
    sid = _sid(db)
    for c in _client_for(db):
        st = _data(c, f"/v1/seasons/{sid}/standings")
        wk = _data(c, f"/v1/seasons/{sid}/weeks/{PENDING_WEEK}/matchups")
        cur = _data(c, "/v1/seasons/current")
    assert st["through_week"] == PENDING_WEEK and st["pending_week"] is None
    assert all(r["wins"] + r["losses"] + r["ties"] == PENDING_WEEK for r in st["rows"])
    hand = _hand_standings(db)
    for r in st["rows"]:
        assert r["points_for"] == pytest.approx(hand[r["team_id"]][3], abs=0.01)
    assert wk["pending"] is False
    assert all(g["team_a"]["score"] is not None and not g["pending"] for g in wk["games"])
    assert cur["last_finalized_week"] == PENDING_WEEK and cur["pending_pairings"] == []


def test_idle_postseason_rows_are_not_games(variant: Any) -> None:
    db = variant(_idle_postseason)
    sid = _sid(db)
    idle_teams = [
        r[0]
        for r in _rows(
            db,
            "SELECT team_id FROM matchups WHERE season_id=? AND week=15 AND opponent_team_id IS NULL",
            sid,
        )
    ]
    assert len(idle_teams) == 2
    for c in _client_for(db):
        wk = _data(c, f"/v1/seasons/{sid}/weeks/15/matchups")
        sched = _data(c, f"/v1/teams/{idle_teams[0]}/schedule")
        trend = _data(c, f"/v1/teams/{idle_teams[0]}/scoring-trend")
        book = _data(c, "/v1/records")
    assert wk["games"] == []
    assert all(g["week"] != 15 for g in sched["games"])
    assert all(p["week"] != 15 for p in trend["points"])
    assert book["highest_team_score"]["value"] != 321.0


# ── /v1/seasons/current ─────────────────────────────────────────────────────


def test_current_season_payload(mixed_client: TestClient, mixed_era_db_path: Path) -> None:
    cur = _data(mixed_client, "/v1/seasons/current")
    assert cur["available"] is True
    assert cur["season_id"] == _sid(mixed_era_db_path)
    assert cur["season_year"] == SLEEPER_YEAR
    assert (cur["platform"], cur["platform_label"]) == ("sleeper", "Sleeper")
    assert cur["last_finalized_week"] == PENDING_WEEK - 1
    assert cur["pending_week"] == PENDING_WEEK
    assert len(cur["latest_results"]) == 6
    assert all(g["team_a"]["score"] is not None for g in cur["latest_results"])
    assert len(cur["pending_pairings"]) == 6
    assert all(g["pending"] and g["team_a"]["score"] is None for g in cur["pending_pairings"])
    assert [r["rank"] for r in cur["standings_top"]] == [1, 2, 3, 4]


def test_current_season_unavailable_off_season(client: TestClient) -> None:
    cur = _data(client, "/v1/seasons/current")
    assert cur == {**cur, "available": False, "reason": "no_current_season"}
    assert cur["latest_results"] == [] and cur["season_id"] is None
