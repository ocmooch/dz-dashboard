"""Sleeper D5: official brackets, the one Sacko rule, potential points, official divisions.

Known answers come from ``tests.sleeper_fixture.decided_brackets()`` (the decided fixture's own
bracket, computed from the raw weekly scores), not from upstream's derived places, so the official
path is checked against an independent answer.
"""

from __future__ import annotations

import shutil
import sqlite3
from typing import TYPE_CHECKING, Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ff_dashboard.analytics.bracket import postseason_classification, season_sacko_map
from ff_dashboard.analytics.brackets import official_sacko, season_brackets
from ff_dashboard.analytics.efficiency import (
    pending_team_weeks,
    season_efficiency,
    season_potential_points,
)
from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine
from tests.conftest import KNOWN
from tests.sleeper_fixture import SLEEPER_LEAGUE, SLEEPER_YEAR, decided_brackets

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

WINNERS_FILE = f"v1_league_{SLEEPER_LEAGUE}_winners_bracket.json"
LOSERS_FILE = f"v1_league_{SLEEPER_LEAGUE}_losers_bracket.json"


def _rows(db: Path, sql: str, *args: Any) -> list[tuple[Any, ...]]:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def _sid(db: Path) -> int:
    return int(_rows(db, "SELECT season_id FROM seasons WHERE year=?", SLEEPER_YEAR)[0][0])


def _team_ids(db: Path) -> dict[int, int]:
    """Sleeper roster number → team_id for 2026."""
    rows = _rows(
        db,
        "SELECT platform_team_key, team_id FROM teams WHERE season_id=?",
        _sid(db),
    )
    return {int(k.rsplit(":", 1)[1]): int(t) for k, t in rows}


def _session(db: Path) -> Iterator[Session]:
    eng = create_readonly_engine(f"sqlite:///{db}")
    with Session(eng) as s:
        yield s
    eng.dispose()


def _client(db: Path) -> Iterator[TestClient]:
    eng = create_readonly_engine(f"sqlite:///{db}")
    with TestClient(create_app(eng, cache=AnalyticsCache(), cors_origins=[])) as c:
        yield c
    eng.dispose()


def _copy(src: Path, dst: Path, *sql: str) -> Path:
    shutil.copy(src, dst)
    c = sqlite3.connect(dst)
    try:
        for stmt in sql:
            c.execute(stmt)
        c.commit()
    finally:
        c.close()
    return dst


def _games(bracket: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return [g for r in bracket[section]["rounds"] for g in r["games"]]


# --- official brackets -------------------------------------------------------------------


def test_decided_bracket_renders_from_official_rows(decided_client: TestClient, decided_db_path):
    sid = _sid(decided_db_path)
    tid = _team_ids(decided_db_path)
    b = decided_client.get(f"/v1/seasons/{sid}/bracket").json()["data"]
    assert b["source"] == "official" and b["is_provisional"] is False
    assert b["consolation_distinguished"] is True

    answer = decided_brackets()
    for section, name in (("playoff_bracket", WINNERS_FILE), ("consolation_bracket", LOSERS_FILE)):
        want = answer[name]
        # byes = the two seeds that first play in round 2
        seeds = {tid[m["t1"]] for m in want if m["r"] == 2 and "t1_from" not in m}
        assert {t["team_id"] for t in b[section]["bye_teams"]} == seeds
        got = {(g["team_a"]["team_id"], g["team_b"]["team_id"]): g for g in _games(b, section)}
        assert len(got) == len(want) == 7
        for m in want:
            g = got[(tid[m["t1"]], tid[m["t2"]])]
            assert g["winner_team_id"] == tid[m["w"]]
            assert g["team_a"]["score"] is not None and g["matchup_id"] is not None
            assert g["is_consolation"] is (section == "consolation_bracket")

    labels = {g["game_label"] for g in _games(b, "playoff_bracket")} - {None}
    assert labels == {"Championship", "3rd Place", "5th Place"}
    labels = {g["game_label"] for g in _games(b, "consolation_bracket")} - {None}
    assert labels == {"7th Place", "9th Place", "11th Place"}

    (title,) = [g for g in _games(b, "playoff_bracket") if g["placement"] == 1]
    champ = _rows(decided_db_path, "SELECT champion_team_id FROM seasons WHERE season_id=?", sid)
    assert title["winner_team_id"] == champ[0][0]


def test_undecided_bracket_shows_seeds_as_provisional(mixed_client: TestClient, mixed_era_db_path):
    b = mixed_client.get(f"/v1/seasons/{_sid(mixed_era_db_path)}/bracket").json()["data"]
    assert b["source"] == "official" and b["is_provisional"] is True
    games = _games(b, "playoff_bracket") + _games(b, "consolation_bracket")
    assert all(g["winner_team_id"] is None and g["matchup_id"] is None for g in games)
    assert all(
        (g[s] or {}).get("score") is None and not (g[s] or {}).get("is_sacko")
        for g in games
        for s in ("team_a", "team_b")
    )
    # round 1 is seeded with the current standings; later rounds wait on their feeders
    (first, *_) = b["playoff_bracket"]["rounds"]
    assert first["games"] and all(g["team_a"] and g["team_b"] for g in first["games"])


def test_legacy_bracket_is_derived(client: TestClient):
    b = client.get(f"/v1/seasons/{KNOWN['season_id'][2017]}/bracket").json()["data"]
    assert b["source"] == "derived" and b["is_provisional"] is False


def test_pending_postseason_week_has_no_result(decided_db_path, tmp_path):
    db = _copy(
        decided_db_path,
        tmp_path / "pending.db",
        "UPDATE matchups SET extra_data=json_set(extra_data,'$.finalized',json('false'))"
        f" WHERE season_id={_sid(decided_db_path)} AND week=8",
    )
    for s in _session(db):
        b = season_brackets(s, _sid(db))
        assert b is not None and b["is_provisional"] is True
        finals = [g for g in _games(b, "playoff_bracket") if g["week"] == 8]
        assert finals and all(g["week_pending"] and g["winner_team_id"] is None for g in finals)
        assert all(g["team_a"]["score"] is None for g in finals)


# --- the Sacko ---------------------------------------------------------------------------


def test_sacko_agrees_official_recorded_and_fixture_answer(decided_db_path):
    sid = _sid(decided_db_path)
    tid = _team_ids(decided_db_path)
    toilet = max(
        (m for m in decided_brackets()[LOSERS_FILE] if m.get("p")), key=lambda m: int(m["p"])
    )
    want = tid[toilet["l"]]
    recorded = _rows(
        decided_db_path, "SELECT last_place_team_id FROM seasons WHERE season_id=?", sid
    )
    assert recorded[0][0] == want
    for s in _session(decided_db_path):
        official = official_sacko(s, sid)
        assert official is not None and official["team_id"] == want
        assert official["source"] == "official" and official["matchup_id"] is not None
        assert postseason_classification(s, sid)["sacko"] == official
        assert season_sacko_map(s)[sid]["team_id"] == want
        b = season_brackets(s, sid)
        assert b is not None
        flagged = [
            g[side]["team_id"]
            for g in _games(b, "consolation_bracket")
            for side in ("team_a", "team_b")
            if g[side] and g[side]["is_sacko"]
        ]
        assert flagged == [want]


def test_no_sacko_while_bracket_undecided(mixed_era_db_path):
    for s in _session(mixed_era_db_path):
        assert official_sacko(s, _sid(mixed_era_db_path)) is None
        assert postseason_classification(s, _sid(mixed_era_db_path))["sacko"] is None


def test_legacy_sacko_keeps_the_derived_rule(session: Session):
    sources = {v["source"] for v in season_sacko_map(session).values()}
    assert sources and "official" not in sources


def test_official_classification_tiers(decided_db_path):
    sid = _sid(decided_db_path)
    for s in _session(decided_db_path):
        c = postseason_classification(s, sid)
        b = season_brackets(s, sid)
        assert b is not None
        by = c["by_matchup_id"]
        for g in _games(b, "playoff_bracket"):
            want = "championship" if g["placement"] == 1 else "playoff"
            assert by[g["matchup_id"]]["tier"] == want
        for g in _games(b, "consolation_bracket"):
            assert by[g["matchup_id"]]["tier"] == "consolation"
        toilet = sorted(m for m, v in by.items() if v["game_label"] == "Toilet Bowl")
        assert len(toilet) == 2 and toilet[0] == c["sacko"]["matchup_id"]  # one game, two rows
        # idle bye / placed rows are never classified as games
        idle = _rows(
            decided_db_path,
            "SELECT matchup_id FROM matchups WHERE season_id=? AND opponent_team_id IS NULL",
            sid,
        )
        assert idle and not {int(m) for (m,) in idle} & set(by)


# --- potential points --------------------------------------------------------------------


def test_potential_points_legacy_known_answer(session: Session, client: TestClient):
    sid = KNOWN["season_id"][2017]
    ice = KNOWN["team_id"][(2017, "ice")]
    pp = season_potential_points(session, sid)
    assert pp[ice]["computed"] == KNOWN["box_optimal_total"]  # 126.0, the hand-solved box
    assert pp[ice]["official"] is None and pp[ice]["uncertain_weeks"] == []
    eff = season_efficiency(session, sid)
    assert eff is not None
    for t in eff["teams"]:
        assert pp[t["team_id"]]["computed"] == t["optimal"]
    # a team with no solvable week is a gap, never 0
    assert any(v["computed"] is None for v in pp.values())
    rows = client.get(f"/v1/seasons/{sid}/standings").json()["data"]["rows"]
    by = {r["team_id"]: r for r in rows}
    assert by[ice]["potential_points"] == 126.0
    assert all(r["potential_points"] != 0 for r in rows)


def test_potential_points_sleeper_cross_check_and_pending(mixed_era_db_path, mixed_client):
    sid = _sid(mixed_era_db_path)
    ppts = {
        int(t): float(v)
        for t, v in _rows(
            mixed_era_db_path,
            "SELECT team_id, json_extract(extra_data,'$.ppts') FROM teams WHERE season_id=?",
            sid,
        )
        if v is not None
    }
    for s in _session(mixed_era_db_path):
        pending = pending_team_weeks(s, sid)
        assert pending and {w for _, w in pending} == {9}
        pp = season_potential_points(s, sid)
        assert {t: v["official"] for t, v in pp.items() if v["official"] is not None} == {
            t: round(v, 2) for t, v in ppts.items()
        }
        assert all(v["weeks"] <= 8 for v in pp.values())  # the unfinished week counts nowhere
        eff = season_efficiency(s, sid)
        assert eff is not None and all(t["weeks"] <= 8 for t in eff["teams"])
    d = mixed_client.get(f"/v1/seasons/{sid}/standings").json()["data"]
    assert d["potential_points_uncertain_weeks"] == list(range(1, 9))  # bench_or_reserve weeks
    assert all(r["potential_points"] is not None for r in d["rows"])


def test_pending_week_scores_do_not_move_potential_points(mixed_era_db_path, tmp_path):
    sid = _sid(mixed_era_db_path)
    db = _copy(
        mixed_era_db_path,
        tmp_path / "rewritten.db",
        "UPDATE team_rosters SET extra_data=json_set(extra_data,'$.platform_points',99.0)"
        f" WHERE season_year={SLEEPER_YEAR} AND week=9",
    )
    for a in _session(mixed_era_db_path):
        for b in _session(db):
            assert season_potential_points(a, sid) == season_potential_points(b, sid)


# --- divisions ---------------------------------------------------------------------------


def test_divisions_not_used_render_nothing(mixed_client: TestClient, mixed_era_db_path):
    d = mixed_client.get(f"/v1/seasons/{_sid(mixed_era_db_path)}/standings").json()["data"]
    assert d["division_source"] is None
    assert all(r["conference_name"] is None for r in d["rows"])


def test_official_divisions_win(mixed_era_db_path, tmp_path):
    sid = _sid(mixed_era_db_path)
    db = _copy(
        mixed_era_db_path,
        tmp_path / "divisions.db",
        f"UPDATE teams SET division = CASE WHEN team_id % 2 = 0 THEN '1' ELSE '2' END"
        f" WHERE season_id={sid}",
    )
    for c in _client(db):
        d = c.get(f"/v1/seasons/{sid}/standings").json()["data"]
        assert d["division_source"] == "official"
        assert {r["conference_name"] for r in d["rows"]} == {"Division 1", "Division 2"}
