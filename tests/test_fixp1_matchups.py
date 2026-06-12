"""fix-P1 / F-13 + F-17 — week-matchup close/blowout flags + entering record."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_dashboard.analytics.matchups import week_matchups
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _games(session: Session, year: int, week: int) -> list[dict[str, Any]]:
    data = week_matchups(session, KNOWN["season_id"][year], week)
    assert data is not None
    return data["games"]


def _team_ref(games: list[dict[str, Any]], team_id: int) -> dict[str, Any]:
    for g in games:
        for side in (g["team_a"], g["team_b"]):
            if side is not None and side["team_id"] == team_id:
                return side
    raise AssertionError(f"team {team_id} not found in week games")


def _game_with(games: list[dict[str, Any]], team_id: int) -> dict[str, Any]:
    for g in games:
        ids = {s["team_id"] for s in (g["team_a"], g["team_b"]) if s is not None}
        if team_id in ids:
            return g
    raise AssertionError(f"game for team {team_id} not found")


def test_blowout_flag(session: Session) -> None:
    games = _games(session, 2016, 1)
    # Maverick 150 - Iceman 80 = 70-pt margin → blowout, not close.
    g = _game_with(games, KNOWN["team_id"][(2016, "mav")])
    assert g["margin"] == 70.0
    assert g["is_blowout"] is True
    assert g["is_close"] is False


def test_close_flag(session: Session) -> None:
    games = _games(session, 2016, 1)
    # Goose 100.5 - Slider 99.5 = 1-pt margin → close, not blowout.
    g = _game_with(games, KNOWN["team_id"][(2016, "goose")])
    assert g["margin"] == 1.0
    assert g["is_close"] is True
    assert g["is_blowout"] is False


def test_neither_flag(session: Session) -> None:
    # Maverick 120 - Goose 110 in wk2 = 10-pt margin → neither close nor blowout.
    g = _game_with(_games(session, 2016, 2), KNOWN["team_id"][(2016, "mav")])
    assert g["margin"] == 10.0
    assert g["is_close"] is False
    assert g["is_blowout"] is False


def test_entering_record_week1_is_zero(session: Session) -> None:
    ref = _team_ref(_games(session, 2016, 1), KNOWN["team_id"][(2016, "mav")])
    assert ref["entering_record"] == {"wins": 0, "losses": 0, "ties": 0}


def test_entering_record_reflects_prior_weeks(session: Session) -> None:
    games = _games(session, 2016, 2)
    # Maverick won wk1 → 1-0-0 entering wk2; Iceman lost wk1 → 0-1-0.
    mav = _team_ref(games, KNOWN["team_id"][(2016, "mav")])
    ice = _team_ref(games, KNOWN["team_id"][(2016, "ice")])
    assert mav["entering_record"] == {"wins": 1, "losses": 0, "ties": 0}
    assert ice["entering_record"] == {"wins": 0, "losses": 1, "ties": 0}
