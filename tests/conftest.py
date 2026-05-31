"""Shared test fixtures, built on a hand-authored SQLite fixture database.

The fixture league ("Danger Zone Test League") encodes *known answers* so the
analytics layer can be checked to the decimal, and it deliberately includes the
data-gap cases Phase 2 must surface honestly (an unscored 2015 season, a DST
starter with no scored points, availability only for the latest season). See
``KNOWN`` at the bottom of this module for the hand-computed expectations the
tests assert against, and ``docs/08_TESTING_STRATEGY.md`` for the rationale.

The fixture is written with a normal (writable) engine; the app under test is
then bound to a *read-only* engine over the same file, so the read-only boundary
is exercised by every integration test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from ff_pipeline.repository.database import Base
from ff_pipeline.repository.models import (
    League,
    Matchup,
    Owner,
    PipelineRun,
    Player,
    PlayerAvailability,
    PlayerStatsRaw,
    PlayerStatsScored,
    Season,
    SourceHealth,
    Team,
    TeamRoster,
    Transaction,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Engine

LEAGUE_ID = "DZTEST"
NOW = datetime(2018, 1, 2, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------


def _add_raw_and_scored(
    session: Session,
    *,
    player_id: int,
    season_id: int,
    season_year: int,
    week: int,
    points: float,
    breakdown: dict[str, float],
) -> None:
    """Insert a raw stat row (REG) and its scored counterpart."""
    raw = PlayerStatsRaw(
        player_id=player_id,
        season_year=season_year,
        week=week,
        season_type="REG",
        source="nflverse",
        stats={"_synthetic": True},
        is_primary=True,
    )
    session.add(raw)
    session.flush()
    session.add(
        PlayerStatsScored(
            stat_id=raw.stat_id,
            season_id=season_id,
            player_id=player_id,
            week=week,
            total_points=points,
            points_breakdown=breakdown,
        )
    )


def _populate(session: Session) -> None:
    session.add(
        League(
            league_id=LEAGUE_ID,
            name="Danger Zone Test League",
            platform="nfl_com",
            current_season_year=2017,
        )
    )

    # --- Owners: three span every season; Slider leaves after 2016; Viper joins in 2017.
    owners = {
        "mav": Owner(league_id=LEAGUE_ID, display_name="Maverick", joined_year=2015),
        "ice": Owner(league_id=LEAGUE_ID, display_name="Iceman", joined_year=2015),
        "goose": Owner(league_id=LEAGUE_ID, display_name="Goose", joined_year=2015),
        "slider": Owner(
            league_id=LEAGUE_ID, display_name="Slider", joined_year=2015, left_year=2016
        ),
        "viper": Owner(league_id=LEAGUE_ID, display_name="Viper", joined_year=2017),
    }
    session.add_all(owners.values())
    session.flush()
    oid = {k: o.owner_id for k, o in owners.items()}

    # --- Seasons. 2015 is the unscored gap; 2016/2017 are scored.
    seasons: dict[int, Season] = {}
    for year in (2015, 2016, 2017):
        s = Season(
            league_id=LEAGUE_ID,
            year=year,
            status="completed",
            regular_season_weeks=2,
            playoff_weeks=1,
        )
        session.add(s)
        seasons[year] = s
    session.flush()
    sid = {year: s.season_id for year, s in seasons.items()}

    # --- Teams per season (owner -> team). Slider in 2015-16; Viper in 2017.
    rosters_by_year = {
        2015: ("mav", "ice", "goose", "slider"),
        2016: ("mav", "ice", "goose", "slider"),
        2017: ("mav", "ice", "goose", "viper"),
    }
    team_id: dict[tuple[int, str], int] = {}
    for year, members in rosters_by_year.items():
        for key in members:
            t = Team(
                season_id=sid[year],
                owner_id=oid[key],
                team_name=f"{owners[key].display_name} {year}",
                team_abbrev=key.upper()[:4],
            )
            session.add(t)
            session.flush()
            team_id[(year, key)] = t.team_id

    # --- Matchups: one game = two rows (team perspective + opponent perspective).
    # (year, week, home_key, home_score, away_key, away_score)
    games: list[tuple[int, int, str, float, str, float]] = [
        # 2015 (scores exist from reconstruction, but no player-level scoring)
        (2015, 1, "mav", 110.0, "ice", 100.0),
        (2015, 1, "slider", 120.0, "goose", 90.0),
        (2015, 2, "goose", 105.0, "mav", 95.0),
        (2015, 2, "slider", 130.0, "ice", 100.0),
        # 2016 — blowout (Mav 150 vs Ice 80) and narrow win (Goose 100.5 vs Slider 99.5)
        (2016, 1, "mav", 150.0, "ice", 80.0),
        (2016, 1, "goose", 100.5, "slider", 99.5),
        (2016, 2, "mav", 120.0, "goose", 110.0),
        (2016, 2, "slider", 95.0, "ice", 90.0),
        # 2017 — highest team score ever (Mav 160.4)
        (2017, 1, "mav", 160.4, "viper", 120.0),
        (2017, 1, "ice", 130.0, "goose", 125.0),
        (2017, 2, "ice", 105.0, "mav", 100.0),
        (2017, 2, "goose", 140.0, "viper", 110.0),
    ]
    # matchup_id of the *perspective* row, keyed (year, week, team_key), so the
    # box-score tests can address a specific matchup.
    matchup_row_id: dict[tuple[int, int, str], int] = {}
    for year, week, home, hs, away, as_ in games:
        ht, at = team_id[(year, home)], team_id[(year, away)]
        home_row = Matchup(
            season_id=sid[year],
            week=week,
            team_id=ht,
            opponent_team_id=at,
            team_score=hs,
            opponent_score=as_,
            is_win=hs > as_ if hs != as_ else None,
        )
        away_row = Matchup(
            season_id=sid[year],
            week=week,
            team_id=at,
            opponent_team_id=ht,
            team_score=as_,
            opponent_score=hs,
            is_win=as_ > hs if hs != as_ else None,
        )
        session.add_all([home_row, away_row])
        session.flush()
        matchup_row_id[(year, week, home)] = home_row.matchup_id
        matchup_row_id[(year, week, away)] = away_row.matchup_id

    # --- Champions/final ranks. Maverick wins 2016 AND 2017 (playoffs), Slider 2015.
    #     2017 champion is NOT the #1 seed (Iceman), proving champ != standings leader.
    seasons[2015].champion_team_id = team_id[(2015, "slider")]
    seasons[2016].champion_team_id = team_id[(2016, "mav")]
    seasons[2017].champion_team_id = team_id[(2017, "mav")]

    # --- Players. P5 is a DST with no scored rows (known gap).
    players = {
        "lamar": Player(name_full="Lamar Jackson", position="QB", nfl_team="BAL", gsis_id="G1"),
        "cmc": Player(name_full="Christian McCaffrey", position="RB", nfl_team="SF", gsis_id="G2"),
        "jjet": Player(name_full="Justin Jefferson", position="WR", nfl_team="MIN", gsis_id="G3"),
        "kelce": Player(name_full="Travis Kelce", position="TE", nfl_team="KC", gsis_id="G4"),
        "dst": Player(name_full="Ravens D/ST", position="DEF", nfl_team="BAL", gsis_id="G5"),
    }
    session.add_all(players.values())
    session.flush()
    pid = {k: p.player_id for k, p in players.items()}

    # --- Scored stats. 2016 + 2017 only (2015 is the unscored gap).
    # 2016: McCaffrey is the season top scorer (55.0); his wk1 30.0 is the week's best.
    _add_raw_and_scored(
        session,
        player_id=pid["cmc"],
        season_id=sid[2016],
        season_year=2016,
        week=1,
        points=30.0,
        breakdown={"rushing": 18.0, "receiving": 12.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["cmc"],
        season_id=sid[2016],
        season_year=2016,
        week=2,
        points=25.0,
        breakdown={"rushing": 15.0, "receiving": 10.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["lamar"],
        season_id=sid[2016],
        season_year=2016,
        week=1,
        points=20.0,
        breakdown={"passing": 16.0, "rushing": 4.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["lamar"],
        season_id=sid[2016],
        season_year=2016,
        week=2,
        points=28.0,
        breakdown={"passing": 20.0, "rushing": 8.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["jjet"],
        season_id=sid[2016],
        season_year=2016,
        week=1,
        points=15.0,
        breakdown={"receiving": 15.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["jjet"],
        season_id=sid[2016],
        season_year=2016,
        week=2,
        points=22.0,
        breakdown={"receiving": 22.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["kelce"],
        season_id=sid[2016],
        season_year=2016,
        week=1,
        points=10.0,
        breakdown={"receiving": 10.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["kelce"],
        season_id=sid[2016],
        season_year=2016,
        week=2,
        points=12.0,
        breakdown={"receiving": 12.0},
    )

    # 2017: Jefferson is the season top scorer (58.0); Lamar's wk1 35.5 is the all-time best week.
    _add_raw_and_scored(
        session,
        player_id=pid["lamar"],
        season_id=sid[2017],
        season_year=2017,
        week=1,
        points=35.5,
        breakdown={"passing": 25.5, "rushing": 10.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["lamar"],
        season_id=sid[2017],
        season_year=2017,
        week=2,
        points=18.0,
        breakdown={"passing": 14.0, "rushing": 4.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["cmc"],
        season_id=sid[2017],
        season_year=2017,
        week=1,
        points=22.0,
        breakdown={"rushing": 14.0, "receiving": 8.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["cmc"],
        season_id=sid[2017],
        season_year=2017,
        week=2,
        points=20.0,
        breakdown={"rushing": 12.0, "receiving": 8.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["jjet"],
        season_id=sid[2017],
        season_year=2017,
        week=1,
        points=28.0,
        breakdown={"receiving": 28.0},
    )
    _add_raw_and_scored(
        session,
        player_id=pid["jjet"],
        season_id=sid[2017],
        season_year=2017,
        week=2,
        points=30.0,
        breakdown={"receiving": 30.0},
    )

    # --- Rosters (minimal): McCaffrey owned by Maverick across 2016-17; the DST is a
    #     starter on Maverick's 2016 team with no scored points (the DST gap case).
    session.add_all(
        [
            TeamRoster(
                team_id=team_id[(2016, "mav")],
                player_id=pid["cmc"],
                season_year=2016,
                week=1,
                roster_slot="RB",
                is_starter=True,
                acquisition_type="draft",
                acquisition_week=1,
            ),
            TeamRoster(
                team_id=team_id[(2017, "mav")],
                player_id=pid["cmc"],
                season_year=2017,
                week=1,
                roster_slot="RB",
                is_starter=True,
                acquisition_type="draft",
                acquisition_week=1,
            ),
            TeamRoster(
                team_id=team_id[(2016, "mav")],
                player_id=pid["dst"],
                season_year=2016,
                week=1,
                roster_slot="DEF",
                is_starter=True,
                acquisition_type="draft",
                acquisition_week=1,
            ),
        ]
    )

    # --- Availability: only the latest season (2017) has it (the current-season-only gap).
    session.add(
        PlayerAvailability(
            player_id=pid["jjet"],
            season_year=2017,
            week=1,
            status="owned",
            owning_team_id=team_id[(2017, "ice")],
            is_pre_kickoff_snapshot=True,
            last_status_change=NOW,
        )
    )

    # --- 2016 draft (the one captured draft; 2015 & 2017 have none → the gap case).
    #     Order is by executed_at, so the n-th row is overall pick n. Authored so
    #     the value metric (season_points - avg of picks within ±2 of the slot) has
    #     a clean, hand-checkable steal and bust:
    #       overall 1  Iceman  → Kelce  (22.0)  expected (22+48+37)/3 = 35.6667 → -13.67  BUST
    #       overall 2  Goose   → Lamar  (48.0)  expected (22+48+37+55)/4 = 40.5  →  +7.50
    #       overall 3  Slider  → Jefferson (37) expected 40.5                    →  -3.50
    #       overall 4  Maverick→ McCaffrey (55) expected (48+37+55)/3 = 46.6667  →  +8.33  STEAL
    #     (McCaffrey is also Maverick's 2016 rostered draftee, so board ↔ roster agree.)
    draft_base = datetime(2016, 9, 1, 18, 0, 0, tzinfo=UTC)
    draft_2016: list[tuple[str, str]] = [
        ("ice", "kelce"),
        ("goose", "lamar"),
        ("slider", "jjet"),
        ("mav", "cmc"),
    ]
    for i, (team_key, player_key) in enumerate(draft_2016):
        session.add(
            Transaction(
                season_id=sid[2016],
                transaction_type="draft",
                executed_at=draft_base + timedelta(minutes=i),
                effective_week=0,
                team_id=team_id[(2016, team_key)],
                player_id=pid[player_key],
                direction="add",
            )
        )

    # --- A hand-solvable box score: Iceman's 2017 week-1 lineup (the ice vs goose
    #     game). A full starter set + bench + an IR player + a DST starter with no
    #     scored points, authored so the optimal-lineup solver has a known answer:
    #       starter total   = 24+18+9+15+11+8+12+7 (+DST 0)      = 104.0
    #       bench points     = 26+20+5 (IR's 30 excluded)         = 51.0
    #       optimal lineup   = swap QB 24->26 and RB 9->20        = 117.0
    #       points left      = 117.0 - 104.0                       = 13.0
    #     Every added point stays under the existing record maxima (best week 35.5,
    #     2017 top scorer 58.0) so no prior KNOWN answer moves.
    box_players = {
        "ice_qb1": Player(name_full="Ice QB One", position="QB", nfl_team="BAL"),
        "ice_qb2": Player(name_full="Ice QB Two", position="QB", nfl_team="CIN"),
        "ice_rb1": Player(name_full="Ice RB One", position="RB", nfl_team="NYG"),
        "ice_rb2": Player(name_full="Ice RB Two", position="RB", nfl_team="DAL"),
        "ice_rb3": Player(name_full="Ice RB Three", position="RB", nfl_team="PHI"),
        "ice_wr1": Player(name_full="Ice WR One", position="WR", nfl_team="GB"),
        "ice_wr2": Player(name_full="Ice WR Two", position="WR", nfl_team="DET"),
        "ice_wr3": Player(name_full="Ice WR Three", position="WR", nfl_team="CHI"),
        "ice_wr4": Player(name_full="Ice WR Four", position="WR", nfl_team="LA"),
        "ice_te1": Player(name_full="Ice TE One", position="TE", nfl_team="KC"),
        "ice_k1": Player(name_full="Ice K One", position="K", nfl_team="BUF"),
        "ice_dst": Player(name_full="Ice D/ST", position="DEF", nfl_team="PIT"),
        "ice_ir": Player(name_full="Ice IR Guy", position="RB", nfl_team="MIA"),
    }
    session.add_all(box_players.values())
    session.flush()
    bpid = {k: p.player_id for k, p in box_players.items()}

    ice_2017 = team_id[(2017, "ice")]
    # (key, slot, is_starter, points)  — points None => no scored row (the DST gap).
    box_lineup: list[tuple[str, str, bool, float | None]] = [
        ("ice_qb1", "QB", True, 24.0),
        ("ice_rb1", "RB", True, 18.0),
        ("ice_rb2", "RB", True, 9.0),
        ("ice_wr1", "WR", True, 15.0),
        ("ice_wr2", "WR", True, 11.0),
        ("ice_te1", "TE", True, 8.0),
        ("ice_wr3", "FLEX", True, 12.0),
        ("ice_k1", "K", True, 7.0),
        ("ice_dst", "DEF", True, None),  # DST starter, not scored (known gap)
        ("ice_qb2", "BN", False, 26.0),
        ("ice_rb3", "BN", False, 20.0),
        ("ice_wr4", "BN", False, 5.0),
        ("ice_ir", "IR", False, 30.0),  # high, but IR — must never enter the optimal
    ]
    for key, slot, starter, pts in box_lineup:
        session.add(
            TeamRoster(
                team_id=ice_2017,
                player_id=bpid[key],
                season_year=2017,
                week=1,
                roster_slot=slot,
                is_starter=starter,
                acquisition_type="draft",
                acquisition_week=1,
            )
        )
        if pts is not None:
            _add_raw_and_scored(
                session,
                player_id=bpid[key],
                season_id=sid[2017],
                season_year=2017,
                week=1,
                points=pts,
                breakdown={"rushing": pts},
            )

    # --- A successful pipeline run so /v1/meta + records reflect a real run id.
    run = PipelineRun(status="success", mode="reconstruct", started_at=NOW, finished_at=NOW)
    session.add(run)
    session.flush()
    session.add(SourceHealth(run_id=run.run_id, source="nflverse", status="ok", rows_added=42))

    session.commit()

    # Stash resolved ids so KNOWN can reference them after the build.
    KNOWN["owner_id"] = oid
    KNOWN["season_id"] = sid
    KNOWN["team_id"] = team_id
    KNOWN["player_id"] = pid
    KNOWN["box_player_id"] = bpid
    KNOWN["matchup_id"] = matchup_row_id
    KNOWN["run_id"] = run.run_id


def _create_writer(url: str) -> Engine:
    """A writable engine in WAL mode (mirrors how Phase 1 owns the file), so
    read-only dashboard connections can run concurrently with a writer."""
    engine = create_engine(url, future=True)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    return engine


def _build_database(db_path: Path) -> None:
    engine = _create_writer(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _populate(session)
    engine.dispose()


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixture_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dzdb") / "fantasy.db"
    _build_database(path)
    return path


@pytest.fixture
def engine(fixture_db_path: Path) -> Iterator[Engine]:
    """Read-only engine over the populated fixture database."""
    eng = create_readonly_engine(f"sqlite:///{fixture_db_path}")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    app = create_app(engine, cache=AnalyticsCache(), cors_origins=[])
    with TestClient(app) as c:
        yield c


@pytest.fixture
def empty_engine(tmp_path: Path) -> Iterator[Engine]:
    """Schema-only database (no rows) — for 503 / 'pipeline never ran' tests."""
    path = tmp_path / "empty.db"
    writer = _create_writer(f"sqlite:///{path}")
    Base.metadata.create_all(writer)
    writer.dispose()
    eng = create_readonly_engine(f"sqlite:///{path}")
    yield eng
    eng.dispose()


@pytest.fixture
def empty_client(empty_engine: Engine) -> Iterator[TestClient]:
    app = create_app(empty_engine, cache=AnalyticsCache(), cors_origins=[])
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Known answers (hand-computed). Ids are filled in during _populate.
# ---------------------------------------------------------------------------

KNOWN: dict[str, Any] = {
    # Coverage
    "seasons_present": [2015, 2016, 2017],
    "seasons_scored": [2016, 2017],
    # Standings 2016 (through week 2): order by wins, then points-for.
    # Maverick 2-0 (270.0) > Goose 1-1 (210.5) > Slider 1-1 (194.5) > Iceman 0-2 (170.0)
    "standings_2016": [
        ("mav", 2, 0, 0, 270.0),
        ("goose", 1, 1, 0, 210.5),
        ("slider", 1, 1, 0, 194.5),
        ("ice", 0, 2, 0, 170.0),
    ],
    # Career championships: Maverick 2 (2016, 2017), Slider 1 (2015), others 0.
    "championships": {"mav": 2, "slider": 1, "ice": 0, "goose": 0, "viper": 0},
    # Head-to-head Maverick vs Iceman (regular season): 3 games, Mav 2-1, no ties.
    "h2h_mav_ice": {"games": 3, "a_wins": 2, "b_wins": 1, "ties": 0},
    # Records
    "highest_team_score": 160.4,  # Maverick, 2017 wk1
    "biggest_blowout_margin": 70.0,  # Maverick 150 - Iceman 80, 2016 wk1
    "highest_player_week": 35.5,  # Lamar Jackson, 2017 wk1
    # Stats
    "top_scorer_2016_season_total": 55.0,  # McCaffrey
    "top_scorer_2017_season_total": 58.0,  # Jefferson
    # Box score — Iceman 2017 wk1 (see the hand-authored lineup in _populate).
    "box_starter_total": 104.0,
    "box_bench_points": 51.0,
    "box_optimal_total": 117.0,
    "box_points_left": 13.0,
    # Draft (2016 is the only captured draft; see the block in _populate).
    "draft_2016_overalls": ["kelce", "lamar", "jjet", "cmc"],  # overall pick order
    "draft_top_steal": {"player": "Christian McCaffrey", "overall": 4, "value": 8.33},
    "draft_top_bust": {"player": "Travis Kelce", "overall": 1, "value": -13.67},
}
