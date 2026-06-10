"""Shared test fixtures, built on a hand-authored SQLite fixture database.

The fixture league ("Danger Zone Test League") encodes *known answers* so the
analytics layer can be checked to the decimal, and it deliberately includes the
data-gap cases Phase 2 must surface honestly (an unscored 2015 season, a DEF
starter whose team/week row is genuinely missing, availability only for the
latest season). DST itself is now scored end-to-end, so scored DEF rows exist for
every scored season and ``dst_scoring_complete`` reads true for the fixture. See
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
    Asset,
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
from sqlalchemy import create_engine, func, select
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

# Q11 team-avatar fixtures. A 1x1 PNG stands in for a real team logo; its
# content-addressed-style relative path is written to disk by ``_build_database``
# under ``<db_dir>/assets``. The other two asset rows are deliberately broken (no
# file on disk; a path that escapes the store) so the avatar route's 404 branches
# are exercised. ``AVATAR_*`` are imported by ``tests/test_team_avatar.py``.
AVATAR_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6200010000050001"
    "0d0a2db40000000049454e44ae426082"
)
AVATAR_REAL_PATH = "aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"
AVATAR_MISSING_PATH = "bb/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png"
AVATAR_TRAVERSAL_PATH = "../escape.png"


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
    nfl_team: str | None = None,
) -> None:
    """Insert a raw stat row (REG) and its scored counterpart.

    ``nfl_team`` carries the per-week NFL team nflverse shipped for that player
    (its current franchise code), which ``queries.player_season_teams`` reads to
    render the season-correct team. Left ``None`` by default so existing rows
    exercise the dashboard's fall-back to the ``players.nfl_team`` snapshot.
    """
    raw = PlayerStatsRaw(
        player_id=player_id,
        season_year=season_year,
        week=week,
        season_type="REG",
        source="nflverse",
        stats={"_synthetic": True},
        is_primary=True,
        nfl_team=nfl_team,
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

    # --- Seasons. 2015 is a synthetic unscored gap; 2016/2017 are scored.
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
    # Most team names default to a "{owner} {year}" alias, but a few carry a
    # distinctive fantasy name so global search can be tested on the *team name*
    # itself, not a mere owner alias (F-45). "Dynasty Crew" is reused across two
    # seasons/owners to exercise most-recent-owner dedup (2016 Goose wins).
    distinctive_team_names: dict[tuple[str, int], str] = {
        ("viper", 2017): "Northvale Scumbags",
        ("slider", 2015): "Dynasty Crew",
        ("goose", 2016): "Dynasty Crew",
    }
    team_id: dict[tuple[int, str], int] = {}
    for year, members in rosters_by_year.items():
        for key in members:
            t = Team(
                season_id=sid[year],
                owner_id=oid[key],
                team_name=distinctive_team_names.get(
                    (key, year), f"{owners[key].display_name} {year}"
                ),
                team_abbrev=key.upper()[:4],
            )
            session.add(t)
            session.flush()
            team_id[(year, key)] = t.team_id

    # --- An upcoming, not-yet-played season (mirrors the live DB's offseason
    # 2026): teams are seeded but no game has been played. The dashboard hides
    # such resultless seasons everywhere — they carry no matchups, so
    # ``played_season_ids`` excludes them and they must never appear in the
    # season selector, the museum timeline, manager trajectories, or the
    # coverage view. It reappears automatically once its first games land.
    upcoming_year = 2018
    upcoming = Season(
        league_id=LEAGUE_ID,
        year=upcoming_year,
        status="in_progress",
        regular_season_weeks=None,
        playoff_weeks=None,
    )
    session.add(upcoming)
    session.flush()
    for key in ("mav", "ice", "goose", "viper"):
        session.add(
            Team(
                season_id=upcoming.season_id,
                owner_id=oid[key],
                team_name=f"{owners[key].display_name} {upcoming_year}",
                team_abbrev=key.upper()[:4],
            )
        )
    session.flush()

    # --- Matchups: one game = two rows (team perspective + opponent perspective).
    # (year, week, home_key, home_score, away_key, away_score)
    games: list[tuple[int, int, str, float, str, float]] = [
        # 2015 (team scores exist, but no player-level scoring in the fixture)
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

    # --- 2015 final ranks + a playoff bracket (week 3, beyond the 2-week regular
    #     season so standings/streaks/season-PF are untouched). This exercises the
    #     fix-P1 derivations: owner-season `result` from final_rank, `made_playoffs`
    #     derived from real (non-consolation) playoff games, and the records era
    #     split — Iceman's 50.0 consolation score is the all-time lowest team score
    #     and lands in an unscored fixture season, proving team records are not
    #     gated by player-scoring coverage.
    final_rank_2015 = {"slider": 1, "mav": 2, "goose": 3, "ice": 4}
    for key, rank in final_rank_2015.items():
        team = session.get(Team, team_id[(2015, key)])
        if team is not None:
            team.final_rank = rank

    # (home_key, home_score, away_key, away_score, is_consolation)
    playoff_2015: list[tuple[str, float, str, float, bool]] = [
        ("slider", 120.0, "mav", 110.0, False),  # championship: Slider over Maverick
        ("goose", 90.0, "ice", 50.0, True),  # consolation (toilet bowl): not "made playoffs"
    ]
    for home, hs, away, as_, consolation in playoff_2015:
        ht, at = team_id[(2015, home)], team_id[(2015, away)]
        session.add_all(
            [
                Matchup(
                    season_id=sid[2015],
                    week=3,
                    team_id=ht,
                    opponent_team_id=at,
                    team_score=hs,
                    opponent_score=as_,
                    is_win=hs > as_ if hs != as_ else None,
                    is_playoff=True,
                    is_consolation=consolation,
                ),
                Matchup(
                    season_id=sid[2015],
                    week=3,
                    team_id=at,
                    opponent_team_id=ht,
                    team_score=as_,
                    opponent_score=hs,
                    is_win=as_ > hs if hs != as_ else None,
                    is_playoff=True,
                    is_consolation=consolation,
                ),
            ]
        )

    # --- Players. The Ravens D/ST is a scored team defense (DST is now scored).
    players = {
        "lamar": Player(name_full="Lamar Jackson", position="QB", nfl_team="BAL", gsis_id="G1"),
        "cmc": Player(name_full="Christian McCaffrey", position="RB", nfl_team="SF", gsis_id="G2"),
        "jjet": Player(name_full="Justin Jefferson", position="WR", nfl_team="MIN", gsis_id="G3"),
        "kelce": Player(name_full="Travis Kelce", position="TE", nfl_team="KC", gsis_id="G4"),
        "dst": Player(name_full="Ravens D/ST", position="DEF", nfl_team="BAL", gsis_id="G5"),
        # A never-rostered nflverse "ghost": shares the "McCaffrey" substring with
        # the rostered cmc and the "SF" nfl_team, but is on no team_rosters row, so
        # league-scoped search (F-44) and the index must exclude it while cmc stays.
        "ghost": Player(name_full="Ghost McCaffrey", position="RB", nfl_team="SF", gsis_id="G6"),
        # A mid-season waiver pickup on Maverick's 2016 team (wk2 only) — exercises
        # the derived-roster-moves "add" path (F-37 tier 1). Distinct name/gsis so it
        # collides with no existing search substring or known answer.
        "wendell": Player(name_full="Waiver Wendell", position="RB", nfl_team="DEN", gsis_id="G7"),
        # Rostered only in the unscored 2015 season (2 weeks) — proves derived
        # roster moves are NOT gated on is_scored (snapshots predate scoring).
        "vince": Player(name_full="Vintage Vince", position="WR", nfl_team="GB", gsis_id="G8"),
        # Rostered in a scored season but held out/bye in NFL.com history. This
        # exercises player charts that must show proven 0-point DNP weeks rather
        # than dropping them as missing scored rows.
        "dnp": Player(name_full="DNP Dana", position="RB", nfl_team="TB", gsis_id="G9"),
        # A long-tenured Raider whose *current* snapshot is the relocated "LV"
        # but who was on "OAK" in 2017. Exercises the season-correct NFL-team
        # read (F-54): season_totals must fold his stored per-week team to the
        # season-era code rather than echo the current snapshot.
        "raider": Player(
            name_full="Relocation Reggie", position="WR", nfl_team="LV", gsis_id="G10"
        ),
    }
    session.add_all(players.values())
    session.flush()
    pid = {k: p.player_id for k, p in players.items()}

    # --- Scored stats. 2016 + 2017 only (2015 is the synthetic unscored gap).
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
    # The Ravens D/ST is scored in 2016 (well under McCaffrey's 55.0 season total
    # and the 35.5 best-week record, so no record moves). This gives 2016 its
    # team-defense coverage, which dst_scoring_complete checks at season grain.
    _add_raw_and_scored(
        session,
        player_id=pid["dst"],
        season_id=sid[2016],
        season_year=2016,
        week=1,
        points=7.0,
        breakdown={"sacks": 3.0, "interceptions": 2.0, "points_allowed": 2.0},
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
    # A beyond-championship week (2017's fantasy championship is week 3; this
    # week-4 row is an NFL post-season week). The week-capped season_totals must
    # exclude it (McCaffrey's 2017 fantasy total stays 42.0, not 72.0); kept under
    # the 35.5 best-week record so no records answer moves.
    _add_raw_and_scored(
        session,
        player_id=pid["cmc"],
        season_id=sid[2017],
        season_year=2017,
        week=4,
        points=30.0,
        breakdown={"rushing": 18.0, "receiving": 12.0},
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
    # Relocation Reggie's 2017 weeks carry nflverse's current franchise code "LV";
    # the season-correct read must fold it to the 2017-era "OAK". Kept low-scoring
    # so he never displaces the leaderboard's top rows (Jefferson 58.0 / cmc 42.0).
    _add_raw_and_scored(
        session,
        player_id=pid["raider"],
        season_id=sid[2017],
        season_year=2017,
        week=1,
        points=6.0,
        breakdown={"receiving": 6.0},
        nfl_team="LV",
    )
    _add_raw_and_scored(
        session,
        player_id=pid["raider"],
        season_id=sid[2017],
        season_year=2017,
        week=2,
        points=5.0,
        breakdown={"receiving": 5.0},
        nfl_team="LV",
    )

    # --- Rosters (minimal): McCaffrey owned by Maverick across 2016-17; the Ravens
    #     D/ST is a scored DEF starter on Maverick's 2016 team (DST scored end-to-end).
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
            # --- mav 2016 week-2 snapshot: a 2-week roster diff scenario for the
            #     derived-roster-moves view (F-37 tier 1). McCaffrey persists (drafted
            #     wk1, kept) → retain; the Ravens D/ST has no wk2 row → drop at wk2;
            #     Waiver Wendell first appears wk2 → add at wk2.
            TeamRoster(
                team_id=team_id[(2016, "mav")],
                player_id=pid["cmc"],
                season_year=2016,
                week=2,
                roster_slot="RB",
                is_starter=True,
                acquisition_type="draft",
                acquisition_week=1,
            ),
            TeamRoster(
                team_id=team_id[(2016, "mav")],
                player_id=pid["wendell"],
                season_year=2016,
                week=2,
                roster_slot="BN",
                is_starter=False,
                acquisition_type="waiver",
                acquisition_week=2,
            ),
            # --- mav 2015 (unscored) two-week snapshot: Vince persists both weeks →
            #     a derivable retain in an unscored season (moves not gated on scoring).
            TeamRoster(
                team_id=team_id[(2015, "mav")],
                player_id=pid["vince"],
                season_year=2015,
                week=1,
                roster_slot="WR",
                is_starter=True,
                acquisition_type="draft",
                acquisition_week=1,
            ),
            TeamRoster(
                team_id=team_id[(2015, "mav")],
                player_id=pid["vince"],
                season_year=2015,
                week=2,
                roster_slot="WR",
                is_starter=True,
                acquisition_type="draft",
                acquisition_week=1,
            ),
            TeamRoster(
                # dnp lives on goose (the away/edge-case team), not the canonical
                # ice box-lineup, so the hand-authored ice roster stays 13 players.
                team_id=team_id[(2017, "goose")],
                player_id=pid["dnp"],
                season_year=2017,
                week=1,
                roster_slot="BN",
                is_starter=False,
                acquisition_type="waiver",
                acquisition_week=1,
                extra_data={
                    "snapshot_kind": "history",
                    "nfl_com_points": 0.0,
                    "opponent": "ATL",
                },
            ),
            TeamRoster(
                team_id=team_id[(2017, "goose")],
                player_id=pid["dnp"],
                season_year=2017,
                week=2,
                roster_slot="BN",
                is_starter=False,
                acquisition_type="waiver",
                acquisition_week=1,
                extra_data={
                    "snapshot_kind": "history",
                    "nfl_com_points": 0.0,
                    "opponent": "Bye",
                },
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

    # --- 2017 recorded transactions: exact transaction log rows now exist upstream.
    session.add_all(
        [
            Transaction(
                season_id=sid[2017],
                transaction_type="waiver_add",
                executed_at=datetime(2017, 9, 12, 10, 15, 0, tzinfo=UTC),
                effective_week=2,
                team_id=team_id[(2017, "ice")],
                player_id=pid["jjet"],
                direction="in",
                waiver_priority_used=4,
                notes="Iceman",
            ),
            Transaction(
                season_id=sid[2017],
                transaction_type="lineup_change",
                executed_at=datetime(2017, 9, 17, 9, 5, 0, tzinfo=UTC),
                effective_week=2,
                team_id=team_id[(2017, "ice")],
                player_id=pid["jjet"],
                notes="Iceman",
                extra_data={"from_slot": "BN", "to_slot": "WR"},
            ),
        ]
    )

    # --- A hand-solvable box score: Iceman's 2017 week-1 lineup (the ice vs goose
    #     game). A full starter set + bench + an IR player + a *scored* DST starter
    #     (9.0), authored so the optimal-lineup solver has a known answer:
    #       starter total   = 24+18+9+15+11+8+12+7 + DST 9         = 113.0
    #       bench points     = 26+20+5 (IR's 30 excluded)          = 51.0
    #       optimal lineup   = swap QB 24->26 and RB 9->20, + DST 9 = 126.0
    #       points left      = 126.0 - 113.0                        = 13.0
    #     The DST only seats in the DEF slot (sole DEF), so it adds 9 to both the
    #     actual and optimal totals and points-left is unchanged. Every added point
    #     stays under the existing record maxima (best week 35.5, 2017 top scorer
    #     58.0) so no prior KNOWN answer moves.
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
        ("ice_dst", "DEF", True, 9.0),  # DST starter, now scored end-to-end
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

    # --- A genuinely-missing DEF row: Goose's 2017 wk1 DST is a starter with no
    #     scored row, so the box score still flags it (reason "team_defense_not_scored")
    #     even though DST is scored at the season level. Goose is the *away* side of
    #     the rendered Iceman matchup, and no KNOWN total asserts that side, so this
    #     exercises the per-row gap path without moving any hand-computed answer.
    goose_dst = Player(name_full="Goose D/ST", position="DEF", nfl_team="DEN")
    session.add(goose_dst)
    session.flush()
    session.add(
        TeamRoster(
            team_id=team_id[(2017, "goose")],
            player_id=goose_dst.player_id,
            season_year=2017,
            week=1,
            roster_slot="DEF",
            is_starter=True,
            acquisition_type="draft",
            acquisition_week=1,
        )
    )

    # --- A player nflverse never scored (no scored row) but carrying an
    #     authoritative ``nfl_com_points`` must show that value, available — not a
    #     "no scored data" gap (the inactive / DNP / bye case). Lives on Goose's
    #     (away) bench, where no KNOWN total is asserted.
    viper_def = Player(name_full="Viper D/ST", position="DEF", nfl_team="MIA")
    session.add(viper_def)
    session.flush()
    session.add(
        TeamRoster(
            team_id=team_id[(2017, "goose")],
            player_id=viper_def.player_id,
            season_year=2017,
            week=1,
            roster_slot="BN",
            is_starter=False,
            acquisition_type="draft",
            acquisition_week=1,
            extra_data={"snapshot_kind": "history", "nfl_com_points": 7.0},
        )
    )

    # --- Zero-point context the box score must explain, again on Goose's bench:
    #       * a player whose NFL team was on bye (extra_data.opponent == "Bye")
    #         scored 0 — labelled "bye", not a fake gap; and
    #       * a 0 that does not cleanly fit (the league scored 0 yet nflverse
    #         credits real production) is flagged "unexpected" with a reason.
    bye_guy = Player(name_full="Bye Week Guy", position="WR", nfl_team="DET")
    mismatch_guy = Player(name_full="Mismatch Guy", position="WR", nfl_team="KC")
    session.add_all([bye_guy, mismatch_guy])
    session.flush()
    session.add(
        TeamRoster(
            team_id=team_id[(2017, "goose")],
            player_id=bye_guy.player_id,
            season_year=2017,
            week=1,
            roster_slot="BN",
            is_starter=False,
            acquisition_type="draft",
            acquisition_week=1,
            extra_data={"snapshot_kind": "history", "nfl_com_points": 0.0, "opponent": "Bye"},
        )
    )
    session.add(
        TeamRoster(
            team_id=team_id[(2017, "goose")],
            player_id=mismatch_guy.player_id,
            season_year=2017,
            week=1,
            roster_slot="BN",
            is_starter=False,
            acquisition_type="draft",
            acquisition_week=1,
            extra_data={"snapshot_kind": "history", "nfl_com_points": 0.0, "opponent": "@LA"},
        )
    )
    # nflverse credits the mismatch player 8.0 even though the league scored 0.
    _add_raw_and_scored(
        session,
        player_id=mismatch_guy.player_id,
        season_id=sid[2017],
        season_year=2017,
        week=1,
        points=8.0,
        breakdown={"receiving": 8.0},
    )

    # --- Avatars (Q11). One real team logo (Maverick 2017) the route streams,
    #     plus two broken assets that must 404 cleanly: a dangling row whose
    #     bytes were never written (Iceman 2017) and a malformed escaping path
    #     (Goose 2017). Viper 2017 keeps a null avatar (the monogram-fallback
    #     case). No JSON schema surfaces the column, so no KNOWN answer moves.
    avatars = {
        "real": Asset(
            league_id=LEAGUE_ID,
            kind="team_avatar",
            source_url="https://example.test/logo-a.png",
            sha256="a" * 64,
            content_type="image/png",
            byte_size=len(AVATAR_PNG),
            storage_path=AVATAR_REAL_PATH,
        ),
        "missing": Asset(
            league_id=LEAGUE_ID,
            kind="team_avatar",
            source_url="https://example.test/logo-b.png",
            sha256="b" * 64,
            content_type="image/png",
            storage_path=AVATAR_MISSING_PATH,
        ),
        "traversal": Asset(
            league_id=LEAGUE_ID,
            kind="team_avatar",
            source_url="https://example.test/logo-c.png",
            sha256="c" * 64,
            content_type="image/png",
            storage_path=AVATAR_TRAVERSAL_PATH,
        ),
    }
    session.add_all(avatars.values())
    session.flush()
    for team_key, asset_key in (("mav", "real"), ("ice", "missing"), ("goose", "traversal")):
        avatar_team = session.get(Team, team_id[(2017, team_key)])
        if avatar_team is not None:
            avatar_team.team_avatar_asset_id = avatars[asset_key].asset_id

    # --- A successful pipeline run so /v1/meta + records reflect a real run id.
    run = PipelineRun(status="success", mode="reconstruct", started_at=NOW, finished_at=NOW)
    session.add(run)
    session.flush()
    session.add(SourceHealth(run_id=run.run_id, source="nflverse", status="ok", rows_added=42))

    # Materialize each player's rostered-season span from team_rosters, mirroring
    # the Phase 1 pipeline's derived first/last_rostered_season columns. The
    # dashboard reads these directly (list_player_index scopes on
    # last_rostered_season), so the fixture must honor the same invariant.
    for rostered_pid, lo, hi in session.execute(
        select(
            TeamRoster.player_id,
            func.min(TeamRoster.season_year),
            func.max(TeamRoster.season_year),
        ).group_by(TeamRoster.player_id)
    ).all():
        rostered_player = session.get(Player, rostered_pid)
        if rostered_player is not None:
            rostered_player.first_rostered_season = int(lo)
            rostered_player.last_rostered_season = int(hi)

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
    # Lay the one real avatar's bytes on disk under the asset store
    # (``<db_dir>/assets``), matching Phase 1's content-addressed layout. The
    # other two asset rows are intentionally left without files.
    real_avatar = db_path.parent / "assets" / AVATAR_REAL_PATH
    real_avatar.parent.mkdir(parents=True, exist_ok=True)
    real_avatar.write_bytes(AVATAR_PNG)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixture_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dzdb") / "fantasy.db"
    _build_database(path)
    return path


@pytest.fixture
def fixture_assets_root(fixture_db_path: Path) -> Path:
    """The on-disk avatar store laid down beside the fixture DB (Q11)."""
    return fixture_db_path.parent / "assets"


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
    # DST is scored (9.0) and counts toward both the starter and optimal totals.
    "box_starter_total": 113.0,
    "box_bench_points": 51.0,
    "box_optimal_total": 126.0,
    "box_points_left": 13.0,
    "box_dst_points": 9.0,
    # Draft (2016 is the only captured draft; see the block in _populate).
    "draft_2016_overalls": ["kelce", "lamar", "jjet", "cmc"],  # overall pick order
    "draft_top_steal": {"player": "Christian McCaffrey", "overall": 4, "value": 8.33},
    "draft_top_bust": {"player": "Travis Kelce", "overall": 1, "value": -13.67},
    # Power ranking 2016 (full season; only 2 weeks, so recent==season PF/game).
    # power = 0.4*z(PF/g) + 0.25*z(all-play win pct) + 0.2*z(win%)
    #       + 0.15*z(recent PF/g), population z across the four teams.
    # Order matches standings here, so every rank_delta is 0.
    "power_2016": {
        "mav": {"power_score": 1.4949, "rank": 1, "pf_per_game": 135.0, "z_win": 1.4142},
        "goose": {"power_score": 0.1006, "rank": 2, "pf_per_game": 105.25},
        "slider": {"power_score": -0.3618, "rank": 3, "pf_per_game": 97.25},
        "ice": {"power_score": -1.2338, "rank": 4, "pf_per_game": 85.0, "z_win": -1.4142},
    },
}
