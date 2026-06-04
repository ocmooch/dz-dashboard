"""fix-P1 / F-10 — derived owner-season result + made_playoffs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.owners import owner_seasons
from tests.conftest import KNOWN

if TYPE_CHECKING:
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


def test_rankless_season_is_a_gap_not_zero(session: Session) -> None:
    # A non-champion 2016 team carries no final_rank and 2016 recorded no playoff
    # bracket → result None, made_playoffs None (gaps, never fabricated).
    ice = _row(session, "ice", 2016)
    assert ice["is_champion"] is False
    assert ice["result"] is None  # rank-less
    assert ice["made_playoffs"] is None  # no bracket recorded that season
    # The champion of a rank-less season is still labelled via champion_team_id.
    assert _row(session, "mav", 2016)["result"] == "Champion"
