"""fix-pass P4 — derived in-season roster moves (F-37 tier 1).

Known answers against the fixture's mav-2016 two-week scenario:
McCaffrey (drafted wk1, kept) → retain; Ravens D/ST (wk1 only) → drop at wk2;
Waiver Wendell (wk2 only) → add at wk2. Plus the no-snapshot gap case and the
not-gated-on-scoring case (mav 2015, unscored, two snapshots).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.transactions import derive_roster_moves
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _by_action(moves: list[dict], action: str) -> list[dict]:
    return [m for m in moves if m["action"] == action]


def test_roster_moves_known_answer(session: Session) -> None:
    mav_2016 = KNOWN["team_id"][(2016, "mav")]
    data = derive_roster_moves(session, mav_2016)
    assert data is not None
    assert data["season_year"] == 2016
    assert data["available"] is True
    assert data["roster_weeks"] == [1, 2]

    adds = _by_action(data["moves"], "add")
    drops = _by_action(data["moves"], "drop")
    retains = _by_action(data["moves"], "retain")

    assert len(adds) == 1 and len(drops) == 1 and len(retains) == 1

    add = adds[0]
    assert add["player_id"] == KNOWN["player_id"]["wendell"]
    assert add["player_name"] == "Waiver Wendell"
    assert add["week"] == 2

    drop = drops[0]
    assert drop["player_id"] == KNOWN["player_id"]["dst"]
    assert drop["player_name"] == "Ravens D/ST"
    assert drop["week"] == 2

    retain = retains[0]
    assert retain["player_id"] == KNOWN["player_id"]["cmc"]
    assert retain["week"] == 1


def test_drafted_opening_player_is_retained_not_added(session: Session) -> None:
    """A player drafted at the opening week is a retain, never a spurious add."""
    mav_2016 = KNOWN["team_id"][(2016, "mav")]
    data = derive_roster_moves(session, mav_2016)
    assert data is not None
    cmc = KNOWN["player_id"]["cmc"]
    cmc_moves = [m for m in data["moves"] if m["player_id"] == cmc]
    assert [m["action"] for m in cmc_moves] == ["retain"]
    assert not any(m["action"] == "add" for m in cmc_moves)


def test_roster_moves_gap_when_no_snapshots(session: Session) -> None:
    """A season with <2 roster snapshots → available:false (DataGap), never zeros."""
    ice_2015 = KNOWN["team_id"][(2015, "ice")]  # no 2015 roster rows for ice
    data = derive_roster_moves(session, ice_2015)
    assert data is not None
    assert data["available"] is False
    assert data["roster_weeks"] == []
    assert data["moves"] == []


def test_roster_moves_not_gated_on_is_scored(session: Session) -> None:
    """An unscored season with >=2 snapshots still derives moves."""
    mav_2015 = KNOWN["team_id"][(2015, "mav")]
    data = derive_roster_moves(session, mav_2015)
    assert data is not None
    assert data["is_scored"] is False
    assert data["available"] is True
    assert data["roster_weeks"] == [1, 2]
    vince_moves = [m for m in data["moves"] if m["player_id"] == KNOWN["player_id"]["vince"]]
    assert [m["action"] for m in vince_moves] == ["retain"]


def test_roster_moves_unknown_team_is_none(session: Session) -> None:
    assert derive_roster_moves(session, 999999) is None
