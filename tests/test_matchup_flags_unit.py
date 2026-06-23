"""Unit + integration coverage for matchup superlative flags.

The pure-function cases drive ``flags_for_game`` with hand-built contexts (no DB,
like the ``solve_optimal`` solver tests); the integration case confirms the box
score and the weekly grid surface the *same* flags for one fixture game.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_dashboard.analytics.matchup_flags import flags_for_game
from ff_dashboard.analytics.matchups import box_score, week_matchups
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _side(
    team_id: int, score: float | None, wins: int = 0, losses: int = 0, ties: int = 0
) -> dict[str, Any]:
    return {
        "team_id": team_id,
        "score": score,
        "entering_record": {"wins": wins, "losses": losses, "ties": ties},
    }


def _ctx(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "max_team_score": None,
        "min_team_score": None,
        "max_combined": None,
        "min_combined": None,
        "monster_team_weeks": [],
    }
    base.update(over)
    return base


def _kinds(*, team_a: dict[str, Any] | None, team_b: dict[str, Any] | None, **kw: Any) -> set[str]:
    flags = flags_for_game(team_a=team_a, team_b=team_b, **kw)
    return {f["kind"] for f in flags}


def test_blowout_not_nailbiter() -> None:
    kinds = _kinds(
        team_a=_side(1, 150.0),
        team_b=_side(2, 90.0),
        winner_team_id=1,
        margin=60.0,
        week=1,
        season_ctx=_ctx(),
        week_ctx={},
    )
    assert "blowout" in kinds and "nailbiter" not in kinds


def test_blowout_threshold_is_inclusive_and_rejects_old_cutoff() -> None:
    common = {
        "team_a": _side(1, 160.0),
        "team_b": _side(2, 100.0),
        "winner_team_id": 1,
        "week": 1,
        "season_ctx": _ctx(),
        "week_ctx": {},
    }
    assert "blowout" in _kinds(margin=60.0, **common)
    assert "blowout" not in _kinds(margin=59.99, **common)
    assert "blowout" not in _kinds(margin=40.0, **common)


def test_nailbiter_not_blowout() -> None:
    kinds = _kinds(
        team_a=_side(1, 100.0),
        team_b=_side(2, 97.0),
        winner_team_id=1,
        margin=3.0,
        week=1,
        season_ctx=_ctx(),
        week_ctx={},
    )
    assert "nailbiter" in kinds and "blowout" not in kinds


def test_season_high_is_one_sided() -> None:
    flags = flags_for_game(
        team_a=_side(1, 168.4),
        team_b=_side(2, 90.0),
        winner_team_id=1,
        margin=78.4,
        week=1,
        season_ctx=_ctx(max_team_score=168.4),
        week_ctx={},
    )
    hi = [f for f in flags if f["kind"] == "season_high"]
    assert len(hi) == 1 and hi[0]["team_id"] == 1


def test_dud_low_team_score() -> None:
    flags = flags_for_game(
        team_a=_side(1, 110.0),
        team_b=_side(2, 61.2),
        winner_team_id=1,
        margin=48.8,
        week=1,
        season_ctx=_ctx(min_team_score=61.2),
        week_ctx={},
    )
    dud = [f for f in flags if f["kind"] == "dud"]
    assert len(dud) == 1 and dud[0]["team_id"] == 2


def test_shootout_and_cold_snap_use_combined() -> None:
    shoot = _kinds(
        team_a=_side(1, 160.0),
        team_b=_side(2, 151.0),
        winner_team_id=1,
        margin=9.0,
        week=1,
        season_ctx=_ctx(max_combined=311.0),
        week_ctx={},
    )
    cold = _kinds(
        team_a=_side(1, 60.0),
        team_b=_side(2, 59.8),
        winner_team_id=1,
        margin=0.2,
        week=1,
        season_ctx=_ctx(min_combined=119.8),
        week_ctx={},
    )
    assert "shootout" in shoot
    assert "cold_snap" in cold


def test_tough_luck_loser_outscored_the_field() -> None:
    # Loser (team 2) scored 151.2 and lost to 160; everyone else scored < 151.2.
    flags = flags_for_game(
        team_a=_side(1, 160.0),
        team_b=_side(2, 151.2),
        winner_team_id=1,
        margin=8.8,
        week=1,
        season_ctx=_ctx(),
        week_ctx={1: 160.0, 2: 151.2, 3: 120.0, 4: 99.0},
    )
    tl = [f for f in flags if f["kind"] == "tough_luck"]
    assert len(tl) == 1 and tl[0]["team_id"] == 2


def test_tough_luck_absent_when_another_team_scored_more() -> None:
    kinds = _kinds(
        team_a=_side(1, 160.0),
        team_b=_side(2, 151.2),
        winner_team_id=1,
        margin=8.8,
        week=1,
        season_ctx=_ctx(),
        week_ctx={1: 160.0, 2: 151.2, 3: 158.0},
    )
    assert "tough_luck" not in kinds


def test_upset_when_winner_entered_far_worse() -> None:
    flags = flags_for_game(
        team_a=_side(1, 110.0, wins=2, losses=6),
        team_b=_side(2, 100.0, wins=7, losses=1),
        winner_team_id=1,
        margin=10.0,
        week=9,
        season_ctx=_ctx(),
        week_ctx={},
    )
    up = [f for f in flags if f["kind"] == "upset"]
    assert len(up) == 1 and up[0]["team_id"] == 1


def test_no_upset_before_min_games() -> None:
    kinds = _kinds(
        team_a=_side(1, 110.0, wins=0, losses=1),
        team_b=_side(2, 100.0, wins=1, losses=0),
        winner_team_id=1,
        margin=10.0,
        week=2,
        season_ctx=_ctx(),
        week_ctx={},
    )
    assert "upset" not in kinds


def test_monster_game_matches_team_and_week() -> None:
    ctx = _ctx(
        monster_team_weeks=[{"team_id": 2, "week": 5, "player_name": "J. Gibbs", "points": 41.6}]
    )
    flags = flags_for_game(
        team_a=_side(1, 120.0),
        team_b=_side(2, 130.0),
        winner_team_id=2,
        margin=10.0,
        week=5,
        season_ctx=ctx,
        week_ctx={},
    )
    mg = [f for f in flags if f["kind"] == "monster_game"]
    assert len(mg) == 1 and mg[0]["team_id"] == 2
    # A monster week for a team not in this game, or a different week, does not flag.
    assert not flags_for_game(
        team_a=_side(1, 120.0),
        team_b=_side(2, 130.0),
        winner_team_id=2,
        margin=10.0,
        week=6,
        season_ctx=ctx,
        week_ctx={},
    )


def test_unscored_game_has_no_flags() -> None:
    flags = flags_for_game(
        team_a=_side(1, None),
        team_b=_side(2, None),
        winner_team_id=None,
        margin=None,
        week=1,
        season_ctx=_ctx(max_team_score=100.0),
        week_ctx={},
    )
    assert flags == []


def test_box_score_and_grid_agree(session: Session) -> None:
    """The box score exposes the same flag kinds (and margin) as the weekly grid
    for the same game — the two views must never disagree."""
    season_id = KNOWN["season_id"][2016]
    grid = week_matchups(session, season_id, 1)
    assert grid is not None
    for game in grid["games"]:
        if game["team_b"] is None:
            continue
        box = box_score(session, game["matchup_id"])
        assert box is not None and box["available"] is True
        assert box["margin"] == game["margin"]
        assert {f["kind"] for f in box["flags"]} == {f["kind"] for f in game["flags"]}
