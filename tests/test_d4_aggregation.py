"""Sleeper D4: cross-era aggregation rules (``docs/sleeper/01`` §5, plan
``docs/plans/sleeper-d4-cross-era-aggregation.md``).

Unit tests per rule, then the BFF on the mixed-era fixture (2015-2018 NFL.com + 2026 Sleeper, weeks
1-8 final, week 9 unfinished). Variants are test-only writes to temp copies; ``src/`` stays
read-only.
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ff_dashboard.analytics import aggregation as agg
from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine
from tests.golden_parity import SEASON_ENDPOINTS, TEAM_ENDPOINTS, build_matrix
from tests.sleeper_fixture import SHARED_OWNERS, SLEEPER_YEAR

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

PENDING_WEEK = 9
LAST_FINAL_WEEK = 8


# ── helpers ──────────────────────────────────────────────────────────────────


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


def _rows(db: Path, sql: str, *args: Any) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return list(con.execute(sql, args))
    finally:
        con.close()


def _client(path: Path) -> Iterator[TestClient]:
    eng = create_readonly_engine(f"sqlite:///{path}")
    with TestClient(create_app(eng, cache=AnalyticsCache(), cors_origins=[])) as c:
        yield c
    eng.dispose()


def _session(path: Path) -> Iterator[Session]:
    eng = create_readonly_engine(f"sqlite:///{path}")
    with Session(eng) as s:
        yield s
    eng.dispose()


def _data(c: TestClient, url: str) -> Any:
    r = c.get(url)
    assert r.status_code == 200, (url, r.text)
    return r.json()["data"]


def _sid(db: Path) -> int:
    return int(_rows(db, "SELECT season_id FROM seasons WHERE year=?", SLEEPER_YEAR)[0][0])


def _owner_id(db: Path, name: str) -> int:
    return int(_rows(db, "SELECT owner_id FROM owners WHERE display_name=?", name)[0][0])


def _departed_owner(db: Path) -> int:
    """An owner with legacy seasons but no 2026 team."""
    sid = _sid(db)
    return int(
        _rows(
            db,
            "SELECT owner_id FROM teams GROUP BY owner_id "
            "HAVING sum(season_id = ?) = 0 ORDER BY owner_id LIMIT 1",
            sid,
        )[0][0]
    )


# ── mutations ────────────────────────────────────────────────────────────────


def _sentinel_live_scores(con: sqlite3.Connection) -> None:
    """Every week-9 (unfinished) live score set to a value nothing else can produce."""
    con.execute(
        "UPDATE matchups SET team_score=987.65, opponent_score=876.54 WHERE week=? AND "
        "season_id=(SELECT season_id FROM seasons WHERE year=?)",
        (PENDING_WEEK, SLEEPER_YEAR),
    )


def _rule(con: sqlite3.Connection, year: int, ppr: float) -> None:
    sid = con.execute("SELECT season_id FROM seasons WHERE year=?", (year,)).fetchone()[0]
    for cat, key, ppu in (("passing", "yds", 0.04), ("receiving", "rec", ppr)):
        con.execute(
            "INSERT INTO scoring_rules (season_id, category, stat_key, points_per_unit, unit_size,"
            " raw_text, created_at, updated_at) VALUES (?,?,?,?,1,?, datetime('now'),"
            " datetime('now'))",
            (sid, cat, key, ppu, f"{cat} {key}"),
        )


def _two_eras(con: sqlite3.Connection) -> None:
    """2015-2017 half-PPR, 2026 full PPR (2018 is unplayed in the fixture)."""
    for year in (2015, 2016, 2017):
        _rule(con, year, 0.5)
    _rule(con, SLEEPER_YEAR, 1.0)


def _three_eras(con: sqlite3.Connection) -> None:
    """2015 half-PPR, 2016 no stored rules, 2017 half-PPR again, 2026 full PPR."""
    _rule(con, 2015, 0.5)
    _rule(con, 2017, 0.5)
    _rule(con, SLEEPER_YEAR, 1.0)


# ── unit: one per `01` §5 rule ──────────────────────────────────────────────


def _txn(**kw: Any) -> SimpleNamespace:
    base = {"transaction_type": "free_agent_add", "status": None, "player_id": 7}
    return SimpleNamespace(**{**base, **kw})


@pytest.mark.parametrize(
    ("txn", "expected"),
    [
        (_txn(), True),
        (_txn(transaction_type="drop"), True),
        (_txn(transaction_type="trade"), True),
        (_txn(transaction_type="waiver_add"), True),  # Sleeper waiver claim that won
        (_txn(transaction_type="lineup_change"), False),
        (_txn(transaction_type="setting_change", player_id=None), False),
        (_txn(transaction_type="draft"), False),
        (_txn(transaction_type="waiver_add", status="failed"), False),
        (_txn(transaction_type="trade", player_id=None), False),  # pick/FAAB leg
    ],
)
def test_is_move(txn: SimpleNamespace, expected: bool) -> None:
    assert agg.is_move(txn) is expected


def test_pct_of_budget_never_invents_zero() -> None:
    assert agg.pct_of_budget(37, 100) == 0.37
    assert agg.pct_of_budget(0, 100) == 0.0  # a real $0 spend
    assert agg.pct_of_budget(37, None) is None
    assert agg.pct_of_budget(None, 100) is None
    assert agg.pct_of_budget(37, 0) is None


def test_normalize_within_season() -> None:
    rows = [
        {"season_id": 1, "v": 10.0},
        {"season_id": 1, "v": 20.0},
        {"season_id": 2, "v": 500.0},  # alone in its season
        {"season_id": 1, "v": None},
    ]
    out = agg.normalize_within_season(rows, "v")
    assert [r["v_z"] for r in out] == [-1.0, 1.0, None, None]
    assert "v_z" not in rows[0]  # inputs untouched


def test_aggregation_note() -> None:
    assert agg.aggregation_note([2015, 2016], [], agg.REASON_IN_PROGRESS) is None
    note = agg.aggregation_note(
        [2016, 2026], [], agg.REASON_IN_PROGRESS, [{"season_year": 2026, "through_week": 8}]
    )
    assert note == {
        "used_seasons": [2016, 2026],
        "excluded_seasons": [],
        "partial_seasons": [{"season_year": 2026, "through_week": 8}],
        "reason": "in_progress_partial",
    }


# ── seasons + eras on the mixed fixture ──────────────────────────────────────


def test_counted_seasons_marks_2026_partial(mixed_era_db_path: Path) -> None:
    for s in _session(mixed_era_db_path):
        counted = agg.counted_seasons(s)
        assert counted[_sid(mixed_era_db_path)] == LAST_FINAL_WEEK
        assert all(t is None for sid, t in counted.items() if sid != _sid(mixed_era_db_path))
        assert agg.partial_seasons(s) == [
            {"season_year": SLEEPER_YEAR, "through_week": LAST_FINAL_WEEK}
        ]


def test_seasons_with_capability(mixed_era_db_path: Path) -> None:
    for s in _session(mixed_era_db_path):
        sleeper_only = agg.seasons_with(s, "faab_failed_bids")
        assert sleeper_only == {_sid(mixed_era_db_path)}
        assert _sid(mixed_era_db_path) in agg.seasons_with(s, "standings")


def test_scoring_eras_split_on_rule_change(mixed_era_db_path: Path, tmp_path: Path) -> None:
    db = _copy(mixed_era_db_path, tmp_path / "eras.db", _two_eras)
    for s in _session(db):
        eras = agg.scoring_eras(s)
    first = {"era_id": 1, "label": f"2015{agg.EN_DASH}2017", "start": 2015, "end": 2017}
    assert eras[2015] == eras[2016] == eras[2017] == first
    assert 2018 not in eras  # unplayed: in no era, and it doesn't break one
    # Open-ended while its season is in progress.
    assert eras[SLEEPER_YEAR] == {
        "era_id": 2,
        "label": f"2026{agg.EN_DASH}",
        "start": 2026,
        "end": None,
    }
    assert agg.scoring_era_count(eras) == 2


def test_scoring_eras_rule_less_season_breaks_era(mixed_era_db_path: Path, tmp_path: Path) -> None:
    db = _copy(mixed_era_db_path, tmp_path / "eras.db", _three_eras)
    for s in _session(db):
        eras = agg.scoring_eras(s)
    assert eras[2015] == {"era_id": 1, "label": "2015", "start": 2015, "end": 2015}
    assert eras[2016] is None  # no stored rules: never guessed
    # Same rules as 2015, but a rule-less season sits between: never assumed continuous.
    assert eras[2017] == {"era_id": 2, "label": "2017", "start": 2017, "end": 2017}
    assert eras[SLEEPER_YEAR] is not None and eras[SLEEPER_YEAR]["era_id"] == 3
    assert agg.scoring_era_count(eras) == 3


def test_no_rules_no_eras(mixed_era_db_path: Path) -> None:
    for s in _session(mixed_era_db_path):
        eras = agg.scoring_eras(s)
    assert set(eras.values()) == {None}
    assert agg.scoring_era_count(eras) == 0


# ── the unfinished week leaks nowhere ────────────────────────────────────────


def _scan_urls(db: Path) -> list[str]:
    """The golden matrix plus every season/team route pointed at 2026 (and week 9 itself)."""
    sid = _sid(db)
    urls = [r.url for r in build_matrix(db) if not r.binary]
    urls += [f"/v1/seasons/{sid}{e}" for e in SEASON_ENDPOINTS]
    urls += [f"/v1/seasons/{sid}/weeks/{w}/matchups" for w in (1, LAST_FINAL_WEEK, PENDING_WEEK)]
    urls += [f"/v1/lab/insights/{sid}", f"/v1/stats/top-scorers?season={SLEEPER_YEAR}"]
    for (tid,) in _rows(db, "SELECT team_id FROM teams WHERE season_id=? ORDER BY team_id", sid):
        urls += [f"/v1/teams/{tid}{e}" for e in TEAM_ENDPOINTS]
    for (mid,) in _rows(
        db, "SELECT min(matchup_id) FROM matchups WHERE season_id=? AND week=?", sid, PENDING_WEEK
    ):
        urls.append(f"/v1/matchups/{mid}/box-score")
    return list(dict.fromkeys(urls))


def test_live_scores_change_no_payload(mixed_era_db_path: Path, tmp_path: Path) -> None:
    """Rewriting every week-9 live score changes nothing anywhere: not a story, a weekly plot, a
    consistency rate, a career total. Exact, and catches derived leaks a value grep can't."""
    sentinel = _copy(mixed_era_db_path, tmp_path / "sentinel.db", _sentinel_live_scores)
    urls = _scan_urls(mixed_era_db_path)
    assert len(urls) > 300

    def fetch_all(db: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in _client(db):
            for u in urls:
                r = c.get(u)
                body = r.json().get("data") if r.status_code == 200 else r.status_code
                out[u] = json.dumps(body, sort_keys=True)
        return out

    base, live = fetch_all(mixed_era_db_path), fetch_all(sentinel)
    changed = [u for u in urls if base[u] != live[u]]
    assert changed == []
    assert not [u for u in urls if "987.65" in live[u] or "876.54" in live[u]]


# ── careers + notes on the mixed fixture ─────────────────────────────────────


def test_career_wlt_sums_legacy_plus_2026_final_weeks(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    oid = _owner_id(mixed_era_db_path, SHARED_OWNERS[0])
    sid = _sid(mixed_era_db_path)
    # Hand sum straight from the rows: regular-season games with a result, 2026 through week 8.
    wins, losses = _rows(
        mixed_era_db_path,
        "SELECT sum(m.is_win = 1), sum(m.is_win = 0) FROM matchups m "
        "JOIN teams t ON t.team_id = m.team_id JOIN seasons s ON s.season_id = m.season_id "
        "WHERE t.owner_id = ? AND m.opponent_team_id IS NOT NULL AND m.is_playoff = 0 "
        "AND m.week <= s.regular_season_weeks "
        "AND (m.season_id != ? OR m.week <= ?)",
        oid,
        sid,
        LAST_FINAL_WEEK,
    )[0]
    career = _data(mixed_client, f"/v1/owners/{oid}")
    assert (career["total_wins"], career["total_losses"]) == (wins, losses)
    seasons = _data(mixed_client, f"/v1/owners/{oid}/seasons")["seasons"]
    assert SLEEPER_YEAR in {r["season_year"] for r in seasons}
    partial = [{"season_year": SLEEPER_YEAR, "through_week": LAST_FINAL_WEEK}]
    assert career["aggregation_note"]["partial_seasons"] == partial
    assert career["aggregation_note"]["reason"] == "in_progress_partial"
    assert SLEEPER_YEAR in career["aggregation_note"]["used_seasons"]


def test_notes_on_every_cross_season_payload(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    a = _owner_id(mixed_era_db_path, SHARED_OWNERS[0])
    b = _owner_id(mixed_era_db_path, SHARED_OWNERS[1])
    partial = [{"season_year": SLEEPER_YEAR, "through_week": LAST_FINAL_WEEK}]
    for url in (
        "/v1/owners",
        "/v1/teams",
        "/v1/owners/rivalry-matrix",
        "/v1/rivalries/insights",
        "/v1/league/stories",
        f"/v1/owners/{a}/seasons",
        f"/v1/owners/{a}/story",
        f"/v1/owners/{a}/trajectory",
        f"/v1/owners/{a}/head-to-head/{b}",
    ):
        note = _data(mixed_client, url)["aggregation_note"]
        assert note is not None, url
        assert note["partial_seasons"] == partial, url
        assert note["excluded_seasons"] == [], url

    records = _data(mixed_client, "/v1/records")
    assert records["aggregation_note"]["reason"] == "season_totals_exclude_in_progress"
    assert records["aggregation_note"]["excluded_seasons"] == [SLEEPER_YEAR]
    assert records["aggregation_note"]["partial_seasons"] == partial
    assert records["best_season_points_for"]["season_year"] != SLEEPER_YEAR


def test_departed_owner_career_has_no_note(
    mixed_client: TestClient, mixed_era_db_path: Path
) -> None:
    oid = _departed_owner(mixed_era_db_path)
    assert _data(mixed_client, f"/v1/owners/{oid}")["aggregation_note"] is None
    assert _data(mixed_client, f"/v1/owners/{oid}/seasons")["aggregation_note"] is None


def test_records_and_stories_carry_scoring_era(mixed_era_db_path: Path, tmp_path: Path) -> None:
    db = _copy(mixed_era_db_path, tmp_path / "eras.db", _three_eras)
    for c in _client(db):
        records = _data(c, "/v1/records")
        stories = _data(c, "/v1/league/stories")
    assert records["scoring_era_count"] == stories["scoring_era_count"] == 3
    hi = records["highest_team_score"]
    assert hi["available"]
    era = hi["scoring_era"]
    if hi["season_year"] == 2016:
        assert era is None
    else:
        assert era is not None and era["start"] <= hi["season_year"]
    blowout = next(s for s in stories["stories"] if s["story_id"] == "biggest-blowout")
    assert "scoring_era" in blowout
    # A career-span card has no season, so no era.
    magnet = next(s for s in stories["stories"] if s["story_id"] == "close-loss-magnet")
    assert magnet.get("scoring_era") is None


def test_draft_type_label(mixed_client: TestClient, mixed_era_db_path: Path) -> None:
    sid = _sid(mixed_era_db_path)
    assert _data(mixed_client, f"/v1/seasons/{sid}/draft")["draft_type"] == "snake"
    legacy = int(_rows(mixed_era_db_path, "SELECT season_id FROM seasons WHERE year=2017")[0][0])
    assert _data(mixed_client, f"/v1/seasons/{legacy}/draft")["draft_type"] is None


# ── legacy-only: nothing new appears ─────────────────────────────────────────


def test_legacy_fixture_notes_all_null(client: TestClient) -> None:
    for url in (
        "/v1/owners",
        "/v1/teams",
        "/v1/owners/rivalry-matrix",
        "/v1/rivalries/insights",
        "/v1/league/stories",
        "/v1/records",
    ):
        assert _data(client, url)["aggregation_note"] is None, url
    owners = _data(client, "/v1/owners")["owners"]
    assert all(o["aggregation_note"] is None for o in owners)
    assert _data(client, "/v1/records")["scoring_era_count"] == 0
