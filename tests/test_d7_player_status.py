"""Sleeper D7: player status — nflverse weekly reports first, the Sleeper snapshot as of kickoff
as the fallback (7-day cutoff), and the Player detail status timeline."""

from __future__ import annotations

import sqlite3
from datetime import date
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from ff_pipeline.repository.models import PlayerStatsRaw, PlayerStatsScored, Season
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ff_dashboard.analytics.matchups import _reserve_eligibility_status
from ff_dashboard.analytics.status_timeline import (
    GAP_REPORTS_NOT_LOADED,
    GAP_STALE_SNAPSHOT,
    MergedStatus,
    for_player,
    player_status_timeline,
    sleeper_status_fields,
    week_kickoff,
)
from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine
from tests.sleeper_fixture import NFLVERSE_2026, SLEEPER_YEAR, STALE_SLEEPER_ID

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _rows(db: Path, sql: str, *args: Any) -> list[tuple[Any, ...]]:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def _pid(db: Path, sleeper_id: str) -> int:
    return int(_rows(db, "SELECT player_id FROM players WHERE sleeper_id=?", sleeper_id)[0][0])


def _data(client: TestClient, url: str) -> Any:
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _game(db: Path, week: int, team_id: int) -> int:
    return int(
        _rows(
            db,
            "SELECT m.matchup_id FROM matchups m JOIN seasons s ON s.season_id=m.season_id "
            "WHERE s.year=? AND m.week=? AND m.team_id=?",
            SLEEPER_YEAR,
            week,
            team_id,
        )[0][0]
    )


def _team_of(db: Path, player_id: int, week: int) -> int:
    return int(
        _rows(
            db,
            "SELECT team_id FROM team_rosters WHERE season_year=? AND week=? AND player_id=?",
            SLEEPER_YEAR,
            week,
            player_id,
        )[0][0]
    )


@pytest.fixture(scope="module")
def scored_db(mixed_era_db_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The mixed-era DB with 2026 marked scored (one reconstruction row, week 1), as the go-live
    rescore leaves it, so 2026 box scores render. Test-only writes to a temp copy."""
    out = tmp_path_factory.mktemp("dzd7") / "fantasy.db"
    src = sqlite3.connect(f"file:{mixed_era_db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    eng = create_engine(f"sqlite:///{out}", future=True)
    try:
        with Session(eng) as ss:
            season = ss.scalars(select(Season).where(Season.year == SLEEPER_YEAR)).one()
            (pid,) = _rows(
                out, "SELECT player_id FROM team_rosters WHERE season_year=? AND week=1", 2026
            )[0]
            raw = PlayerStatsRaw(
                player_id=pid, season_year=SLEEPER_YEAR, week=1, source="d7_test", is_primary=True
            )
            ss.add(raw)
            ss.flush()
            ss.add(
                PlayerStatsScored(
                    stat_id=raw.stat_id,
                    season_id=season.season_id,
                    player_id=pid,
                    week=1,
                    total_points=1.0,
                )
            )
            ss.commit()
    finally:
        eng.dispose()
    return out


@pytest.fixture
def scored_client(scored_db: Path, fixture_db_path: Path) -> Iterator[TestClient]:
    eng = create_readonly_engine(f"sqlite:///{scored_db}")
    app = create_app(
        eng, cache=AnalyticsCache(), cors_origins=[], assets_root=fixture_db_path.parent / "assets"
    )
    with TestClient(app) as c:
        yield c
    eng.dispose()


# --- pure helpers ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "week", "expected"),
    [
        (2010, 1, date(2010, 9, 9)),
        (2025, 1, date(2025, 9, 4)),
        (2026, 1, date(2026, 9, 10)),
        (2026, 9, date(2026, 11, 5)),
    ],
)
def test_week_kickoff(year: int, week: int, expected: date) -> None:
    assert week_kickoff(year, week) == expected


def _snap(**kw: Any) -> Any:
    base = {
        "injury_status": None,
        "injury_body_part": None,
        "practice_participation": None,
        "depth_chart_position": None,
        "depth_chart_order": None,
        "nfl_team": None,
        "as_of_date": date(2026, 10, 21),
    }
    return SimpleNamespace(**{**base, **kw})


def test_sleeper_vocabulary_mapping() -> None:
    q = sleeper_status_fields(_snap(injury_status="Questionable", injury_body_part="Knee"))
    assert (q["injury_status"], q["roster_status"], q["injury_body_part"]) == (
        "Questionable",
        None,
        "Knee",
    )
    assert sleeper_status_fields(_snap(injury_status="Out"))["injury_status"] == "Out"
    for code in ("IR", "PUP", "Sus", "NA", "COV", "DNR", "SomethingNew"):
        f = sleeper_status_fields(_snap(injury_status=code))
        assert f["injury_status"] is None  # never a badge
        assert f["roster_status"] == code  # kept for the timeline
    practice = {
        p: sleeper_status_fields(_snap(practice_participation=p))["injury_practice_status"]
        for p in ("Full", "Limited", "DNP", "Weird")
    }
    assert practice == {"Full": "Full", "Limited": "Ltd", "DNP": "DNP", "Weird": None}
    depth = sleeper_status_fields(_snap(depth_chart_position="WR", depth_chart_order=2))
    assert depth["depth_chart"] == "WR2"
    empty = sleeper_status_fields(None)
    assert all(v is None for v in empty.values())


def _merged(source: str | None, status: str | None, **kw: Any) -> MergedStatus:
    return MergedStatus(
        injury_status=status,
        injury_body_part=kw.get("body"),
        injury_secondary=None,
        injury_practice_status=None,
        injury_source=source,
        injury_as_of=date(2026, 10, 21) if source == "sleeper" else None,
        sleeper_roster_status=None,
    )


def test_played_player_suppression() -> None:
    # A Wednesday "Out" on a player who then played is stale: dropped, source cleared.
    out = for_player({1: _merged("sleeper", "Out")}, 1, played=True)
    assert (out["injury_status"], out["injury_source"], out["injury_as_of"]) == (None, None, None)
    # Body part survives; the source stays with it.
    kept = for_player({1: _merged("sleeper", "Out", body="Knee")}, 1, played=True)
    assert (kept["injury_status"], kept["injury_source"]) == (None, "sleeper")
    # Questionable is compatible with playing; DNP keeps Out; nflverse rows are untouched.
    assert for_player({1: _merged("sleeper", "Questionable")}, 1, played=True)["injury_status"] == (
        "Questionable"
    )
    assert for_player({1: _merged("sleeper", "Out")}, 1, played=False)["injury_status"] == "Out"
    assert for_player({1: _merged("nflverse", "Out")}, 1, played=True)["injury_status"] == "Out"
    assert for_player({}, 1, played=True)["injury_source"] is None


def test_reserve_eligibility_takes_sleeper_roster_status() -> None:
    row = SimpleNamespace(roster_slot="IR", extra_data={})
    empty = {
        "injury_status": None,
        "injury_body_part": None,
        "injury_secondary": None,
        "injury_practice_status": None,
    }
    status = _reserve_eligibility_status(
        row, None, empty, player_played=False, sleeper_roster_status="PUP"
    )
    assert status == "PUP"
    # NFL.com roster fields still win.
    nfl = SimpleNamespace(roster_slot="IR", extra_data={"player_status": "IR"})
    assert (
        _reserve_eligibility_status(
            nfl, None, empty, player_played=False, sleeper_roster_status="PUP"
        )
        == "IR"
    )
    # A did-not-play status on a player who played is dropped; the slot is the fallback.
    assert (
        _reserve_eligibility_status(
            row, None, empty, player_played=True, sleeper_roster_status="PUP"
        )
        == "IR"
    )


# --- timeline -------------------------------------------------------------------------------


def test_timeline_stale_snapshot_is_a_gap(mixed_client: TestClient, mixed_era_db_path: Path):
    pid = _pid(mixed_era_db_path, STALE_SLEEPER_ID)
    body = _data(mixed_client, f"/v1/players/{pid}/status?season={SLEEPER_YEAR}")
    assert body["available"] is True
    assert body["platform"] == "sleeper" and body["has_snapshots"] is True
    assert body["snapshot_capability"]["state"] == "available"
    assert body["is_provisional"] is True
    weeks = {w["week"]: w for w in body["weeks"]}
    assert weeks[7]["snapshot"]["as_of"] == "2026-10-21"
    assert weeks[7]["snapshot"]["roster_status"] == "IR"
    assert weeks[7]["snapshot"]["injury_status"] is None
    # 8 days old at week 8's kickoff: past the 7-day cutoff.
    for wk in (8, 9):
        assert weeks[wk]["snapshot"] is None
        assert weeks[wk]["snapshot_gap"] == GAP_STALE_SNAPSHOT
    # No capture before week 7 at all.
    assert weeks[1]["snapshot_gap"] == GAP_STALE_SNAPSHOT


def test_timeline_uses_newest_snapshot_before_kickoff(mixed_client, mixed_era_db_path) -> None:
    sid, week, status, body = NFLVERSE_2026[0]
    pid = _pid(mixed_era_db_path, sid)
    data = _data(mixed_client, f"/v1/players/{pid}/status?season={SLEEPER_YEAR}")
    weeks = {w["week"]: w for w in data["weeks"]}
    # the week-8 snapshot (10-28) is after week 7's kickoff (10-22): ignored for week 7.
    assert weeks[week]["snapshot"]["as_of"] == "2026-10-21"
    assert weeks[8]["snapshot"]["as_of"] == "2026-10-28"
    report = weeks[week]["game_report"]
    assert (report["source"], report["injury_status"], report["injury_body_part"]) == (
        "nflverse",
        status,
        body,
    )
    # Not on the report (≤ the last reported week) is a real answer; after it is a gap.
    assert weeks[8]["game_report"] is None and weeks[8]["game_report_gap"] is None
    assert weeks[9]["game_report_gap"] == GAP_REPORTS_NOT_LOADED


def test_timeline_latest_seven_day_cutoff(mixed_era_db_path: Path) -> None:
    sid = NFLVERSE_2026[0][0]
    pid = _pid(mixed_era_db_path, sid)
    eng = create_readonly_engine(f"sqlite:///{mixed_era_db_path}")
    try:
        with Session(eng) as s:
            exactly_7 = player_status_timeline(s, pid, SLEEPER_YEAR, today=date(2026, 11, 11))
            eight = player_status_timeline(s, pid, SLEEPER_YEAR, today=date(2026, 11, 12))
    finally:
        eng.dispose()
    assert exactly_7 is not None and eight is not None
    assert exactly_7["latest"]["as_of"] == date(2026, 11, 4)
    assert eight["latest"] is None


def test_timeline_legacy_season_has_no_snapshot_column(client: TestClient, fixture_db_path):
    pid, year = _rows(fixture_db_path, "SELECT player_id, season_year FROM player_injury_reports")[
        0
    ]
    body = _data(client, f"/v1/players/{pid}/status?season={year}")
    assert body["available"] is True
    assert body["has_snapshots"] is False
    assert body["latest"] is None and body["is_provisional"] is False
    assert body["snapshot_capability"]["state"] != "available"
    assert all(w["snapshot"] is None and w["snapshot_gap"] is None for w in body["weeks"])
    assert any(w["game_report"] is not None for w in body["weeks"])


def test_timeline_unknown_player_and_unplayed_season(client: TestClient, fixture_db_path) -> None:
    assert client.get("/v1/players/999999/status").status_code == 404
    (pid,) = _rows(fixture_db_path, "SELECT player_id FROM players LIMIT 1")[0]
    body = _data(client, f"/v1/players/{pid}/status?season=2099")
    assert body["available"] is False and body["reason"] == "season_not_played"
    assert body["weeks"] == []


def test_timeline_defaults_to_latest_rostered_season(mixed_client, mixed_era_db_path) -> None:
    pid = _pid(mixed_era_db_path, STALE_SLEEPER_ID)
    assert _data(mixed_client, f"/v1/players/{pid}/status")["season_year"] == SLEEPER_YEAR


# --- box score / team roster ----------------------------------------------------------------


def _box_row(client: TestClient, db: Path, player_id: int, week: int) -> dict[str, Any]:
    team = _team_of(db, player_id, week)
    body = _data(client, f"/v1/matchups/{_game(db, week, team)}/box-score")
    assert body["available"] is True, body["reason"]
    side = body["home"] if body["home"]["team_id"] == team else body["away"]
    return next(p for p in side["lineup"] if p["player_id"] == player_id)


def test_box_score_nflverse_wins_over_snapshot(scored_client, scored_db) -> None:
    sid, week, status, body = NFLVERSE_2026[0]  # Questionable in the Sleeper directory
    row = _box_row(scored_client, scored_db, _pid(scored_db, sid), week)
    assert (row["injury_status"], row["injury_body_part"]) == (status, body)
    assert (row["injury_source"], row["injury_as_of"]) == ("nflverse", None)


def test_box_score_sleeper_fallback_badge(scored_client, scored_db) -> None:
    # Questionable in the directory, no nflverse row in week 7.
    pid = _pid(scored_db, NFLVERSE_2026[1][0])
    row = _box_row(scored_client, scored_db, pid, 7)
    assert row["injury_status"] == "Questionable"
    assert (row["injury_source"], row["injury_as_of"]) == ("sleeper", "2026-10-21")


def test_box_score_snapshot_roster_status_is_not_a_badge(scored_client, scored_db) -> None:
    row = _box_row(scored_client, scored_db, _pid(scored_db, STALE_SLEEPER_ID), 7)
    assert row["injury_status"] is None and row["injury_source"] is None


def test_team_roster_matches_box_score(scored_client, scored_db) -> None:
    sid, week, status, _ = NFLVERSE_2026[0]
    pid = _pid(scored_db, sid)
    team = _team_of(scored_db, pid, week)
    roster = _data(scored_client, f"/v1/teams/{team}/roster?week={week}")
    row = next(p for p in roster["players"] if p["player_id"] == pid)
    assert (row["injury_status"], row["injury_source"]) == (status, "nflverse")
    fallback = _pid(scored_db, NFLVERSE_2026[1][0])
    team7 = _team_of(scored_db, fallback, 7)
    roster7 = _data(scored_client, f"/v1/teams/{team7}/roster?week=7")
    row7 = next(p for p in roster7["players"] if p["player_id"] == fallback)
    assert (row7["injury_source"], row7["injury_as_of"]) == ("sleeper", "2026-10-21")


def test_legacy_box_score_source_is_nflverse_or_null(client: TestClient, fixture_db_path) -> None:
    year, week = _rows(fixture_db_path, "SELECT season_year, week FROM player_injury_reports")[0]
    mids = _rows(
        fixture_db_path,
        "SELECT m.matchup_id FROM matchups m JOIN seasons s ON s.season_id=m.season_id "
        "WHERE s.year=? AND m.week=?",
        year,
        week,
    )
    rows = []
    for (mid,) in mids:
        body = _data(client, f"/v1/matchups/{mid}/box-score")
        rows += [p for side in (body["home"], body["away"]) if side for p in side["lineup"]]
    assert rows and {p["injury_source"] for p in rows} <= {"nflverse", None}
    assert all(p["injury_as_of"] is None for p in rows)
    assert all((p["injury_source"] is None) == (p["injury_status"] is None) for p in rows)
