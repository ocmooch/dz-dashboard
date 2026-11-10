"""Sleeper D3: the shared game-state rule (pure; no DB)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ff_dashboard.analytics.game_state import (
    commissioner_override,
    game_result,
    is_final_game,
    is_game,
    is_idle,
    is_pending,
)


def _m(**kw: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "opponent_team_id": 2,
        "team_score": 100.0,
        "opponent_score": 90.0,
        "is_win": True,
        "extra_data": None,
    }
    return SimpleNamespace(**{**base, **kw})


def test_legacy_row_is_a_final_game() -> None:
    m = _m()
    assert is_game(m) and is_final_game(m) and not is_pending(m)
    assert game_result(m) == "W"
    assert game_result(_m(is_win=False)) == "L"
    assert game_result(_m(is_win=None, opponent_score=100.0)) == "T"


def test_unfinished_week_is_never_a_result() -> None:
    m = _m(is_win=None, extra_data={"finalized": False})
    assert is_pending(m) and not is_final_game(m)
    assert game_result(m) is None  # not a tie, though both live scores exist
    assert not is_pending(_m(extra_data={"finalized": True}))


def test_idle_postseason_row_is_not_a_game() -> None:
    m = _m(
        opponent_team_id=None,
        opponent_score=None,
        is_win=None,
        extra_data={"postseason_role": "bye"},
    )
    assert not is_game(m) and is_idle(m) and not is_final_game(m)
    assert game_result(m) is None
    # a legacy opponent-less row is not tagged idle (legacy output unchanged)
    assert not is_idle(_m(opponent_team_id=None))


def test_commissioner_override_carries_both_values() -> None:
    m = _m(extra_data={"points_official": 112.46, "custom_points": 117.46})
    assert commissioner_override(m) == {"official": 112.46, "custom": 117.46}
    assert commissioner_override(_m(extra_data={"points_official": 112.46})) is None
    assert commissioner_override(_m()) is None
