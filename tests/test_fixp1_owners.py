"""fix-P1 / F-10 — derived owner-season result + made_playoffs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.database import Base
from ff_pipeline.repository.models import League, Matchup, Owner, Season, Team
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession

from ff_dashboard.analytics.owners import owner_seasons
from ff_dashboard.engine import create_readonly_engine
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


def _row(session: Session, owner_key: str, year: int) -> dict:
    rows = owner_seasons(session, KNOWN["owner_id"][owner_key])
    assert rows is not None
    return next(r for r in rows if r["season_year"] == year)


def test_champion_result_and_made_playoffs(session: Session) -> None:
    # Slider won 2015 in a real (non-consolation) playoff game.
    slider = _row(session, "slider", 2015)
    assert slider["result"] == "Champion"
    assert slider["made_playoffs"] is True


def test_runner_up_result(session: Session) -> None:
    # Maverick lost the 2015 championship game → final_rank 2 → Runner-up, made playoffs.
    mav = _row(session, "mav", 2015)
    assert mav["result"] == "Runner-up"
    assert mav["made_playoffs"] is True


def test_consolation_game_is_not_made_playoffs(session: Session) -> None:
    # Goose/Iceman played only the 2015 consolation game → did NOT make the playoffs,
    # even though it carries is_playoff=True (the toilet-bowl caveat).
    goose = _row(session, "goose", 2015)
    assert goose["result"] == "3rd place"
    assert goose["made_playoffs"] is False
    ice = _row(session, "ice", 2015)
    assert ice["result"] == "4th"
    assert ice["made_playoffs"] is False


def test_pre_2016_result_is_populated(session: Session) -> None:
    # The whole point of F-10: completed pre-2016 seasons carry a result string.
    assert _row(session, "slider", 2015)["result"] is not None


def test_owner_seasons_excludes_unplayed_season(session: Session) -> None:
    # Maverick has a seeded team in the upcoming 2018 season, but it has played
    # no games — it must not appear as a resultless row in his season table.
    rows = owner_seasons(session, KNOWN["owner_id"]["mav"])
    assert rows is not None
    assert 2018 not in {r["season_year"] for r in rows}


def test_undiscriminating_bracket_yields_none(tmp_path: Path) -> None:
    # Mirrors the real-data shape: is_consolation is unpopulated and *every* team
    # carries an is_playoff game, so the bracket can't be told apart → made_playoffs
    # must be None (unknown), never a fabricated True. result still derives normally.
    db = tmp_path / "undiscriminating.db"
    weng = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(weng)
    with SASession(weng) as s:
        s.add(League(league_id="U", name="U", platform="nfl_com", current_season_year=2020))
        o1, o2 = Owner(league_id="U", display_name="A"), Owner(league_id="U", display_name="B")
        s.add_all([o1, o2])
        s.flush()
        oid1 = o1.owner_id
        season = Season(
            league_id="U", year=2020, status="completed", regular_season_weeks=1, playoff_weeks=1
        )
        s.add(season)
        s.flush()
        t1 = Team(season_id=season.season_id, owner_id=o1.owner_id, team_name="A20", final_rank=1)
        t2 = Team(season_id=season.season_id, owner_id=o2.owner_id, team_name="B20", final_rank=2)
        s.add_all([t1, t2])
        s.flush()
        season.champion_team_id = t1.team_id
        # A regular game and a playoff game — both teams flagged is_playoff, none
        # marked consolation (the undiscriminating real-data shape).
        for asc, bsc, wk, playoff in [(100.0, 90.0, 1, False), (110.0, 95.0, 2, True)]:
            s.add_all(
                [
                    Matchup(
                        season_id=season.season_id,
                        week=wk,
                        team_id=t1.team_id,
                        opponent_team_id=t2.team_id,
                        team_score=asc,
                        opponent_score=bsc,
                        is_win=asc > bsc,
                        is_playoff=playoff,
                    ),
                    Matchup(
                        season_id=season.season_id,
                        week=wk,
                        team_id=t2.team_id,
                        opponent_team_id=t1.team_id,
                        team_score=bsc,
                        opponent_score=asc,
                        is_win=bsc > asc,
                        is_playoff=playoff,
                    ),
                ]
            )
        s.commit()
    weng.dispose()

    reng = create_readonly_engine(f"sqlite:///{db}")
    with SASession(reng) as s:
        rows = owner_seasons(s, oid1)
        assert rows is not None
        assert rows[0]["made_playoffs"] is None  # undiscriminating bracket → unknown
        assert rows[0]["result"] == "Champion"  # result still derives
    reng.dispose()


def test_rankless_season_is_a_gap_not_zero(session: Session) -> None:
    # A non-champion 2016 team carries no final_rank and 2016 recorded no playoff
    # bracket → result None, made_playoffs None (gaps, never fabricated).
    ice = _row(session, "ice", 2016)
    assert ice["is_champion"] is False
    assert ice["result"] is None  # rank-less
    assert ice["made_playoffs"] is None  # no bracket recorded that season
    # The champion of a rank-less season is still labelled via champion_team_id.
    assert _row(session, "mav", 2016)["result"] == "Champion"
