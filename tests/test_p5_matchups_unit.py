"""P5 — matchups & box-score unit tests against the fixture's known answers.

The optimal-lineup solver is checked to the decimal both as a standalone matroid
solver and end-to-end through the hand-authored Iceman 2017 wk1 box score.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.matchups import (
    box_score,
    slot_accepts,
    solve_optimal,
    week_matchups,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --- Optimal-lineup solver (standalone) ------------------------------------


def test_solver_seats_best_player_per_dedicated_slot() -> None:
    players = [
        {"position": "QB", "points": 10.0},
        {"position": "QB", "points": 25.0},  # the better QB
        {"position": "RB", "points": 12.0},
    ]
    assert solve_optimal(players, ["QB", "RB"]) == 37.0  # 25 + 12


def test_solver_uses_flex_for_the_best_leftover() -> None:
    # One RB slot + one FLEX(RB/WR/TE). The FLEX should take the second RB (20)
    # over the lone WR (5), proving eligibility-aware assignment, not naive fill.
    players = [
        {"position": "RB", "points": 18.0},
        {"position": "RB", "points": 20.0},
        {"position": "WR", "points": 5.0},
    ]
    assert solve_optimal(players, ["RB", "FLEX"]) == 38.0  # 20 + 18, WR benched


def test_solver_respects_position_exclusivity() -> None:
    # A QB can't fill a WR slot; with no eligible WR the slot stays empty.
    players = [{"position": "QB", "points": 30.0}]
    assert solve_optimal(players, ["QB", "WR"]) == 30.0


def test_solver_is_order_independent() -> None:
    a = [
        {"position": "WR", "points": 9.0},
        {"position": "RB", "points": 20.0},
        {"position": "RB", "points": 18.0},
    ]
    assert solve_optimal(a, ["RB", "RB", "FLEX"]) == 47.0  # 20 + 18 + 9


def test_solver_recognizes_nfl_com_flex_slot_names() -> None:
    # Phase 1 stores NFL.com's flex slots as "R/W/T" (RB/WR/TE) and "W/R"
    # (WR/RB). An eligible player must be seatable in them, or the optimal would
    # silently undercount a whole flex slot (a real bug caught on live data).
    players = [{"position": "TE", "points": 14.0}, {"position": "WR", "points": 22.0}]
    assert solve_optimal(players, ["R/W/T"]) == 22.0  # WR wins the RB/WR/TE flex
    assert solve_optimal(players, ["W/R"]) == 22.0  # W/R accepts the WR
    assert solve_optimal([{"position": "TE", "points": 14.0}], ["W/R"]) == 0.0  # TE not in W/R


def test_slot_accepts_rules() -> None:
    assert slot_accepts("R/W/T", "RB") is True
    assert slot_accepts("R/W/T", "QB") is False
    assert slot_accepts("W/R", "TE") is False
    assert slot_accepts("DEF", "DEF") is True
    assert slot_accepts("WAT", "WAT") is True  # unknown slot -> exact-match fallback
    assert slot_accepts(None, "RB") is False


# --- Box score (end-to-end against the hand-authored lineup) ---------------


def _ice_box(session: Session) -> dict:
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = box_score(session, mid)
    assert data is not None
    assert data["available"] is True
    # Iceman is the perspective ("home") team of this matchup row.
    return data["home"]


def test_box_starter_total(session: Session) -> None:
    assert _ice_box(session)["starter_points"] == KNOWN["box_starter_total"]  # 104.0


def test_box_optimal_and_points_left(session: Session) -> None:
    home = _ice_box(session)
    assert home["optimal_total"] == KNOWN["box_optimal_total"]  # 117.0
    assert home["points_left_on_bench"] == KNOWN["box_points_left"]  # 13.0


def test_box_bench_points_excludes_ir(session: Session) -> None:
    # 26 + 20 + 5 = 51; the IR player's 30 must not count.
    assert _ice_box(session)["bench_points"] == KNOWN["box_bench_points"]  # 51.0


def test_box_ir_never_enters_optimal(session: Session) -> None:
    # The IR player scores 30 (more than any bench RB) but is ineligible; if it
    # leaked into the optimal, the total would exceed 117.
    assert _ice_box(session)["optimal_total"] == 117.0


def test_box_dst_starter_is_a_gap_not_a_zero(session: Session) -> None:
    home = _ice_box(session)
    dst = next(p for p in home["lineup"] if p["position"] == "DEF")
    assert dst["is_starter"] is True
    assert dst["league_points"] is None  # never 0
    assert dst["available"] is False
    assert dst["reason"] == "team_defense_not_scored"


def test_box_authoritative_total_and_winner(session: Session) -> None:
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = box_score(session, mid)
    assert data is not None
    assert data["home"]["total_score"] == 130.0  # the real game score
    assert data["away"]["total_score"] == 125.0
    assert data["winner_team_id"] == KNOWN["team_id"][(2017, "ice")]


def test_box_pre_2016_season_is_unscored_gap(session: Session) -> None:
    mid = KNOWN["matchup_id"][(2015, 1, "mav")]
    data = box_score(session, mid)
    assert data is not None
    assert data["available"] is False
    assert data["reason"] == "season_unscored"


def test_box_unknown_matchup_returns_none(session: Session) -> None:
    assert box_score(session, 999999) is None


# --- Week matchups (deduped cards) -----------------------------------------


def test_week_matchups_dedupe_to_one_card_per_game(session: Session) -> None:
    data = week_matchups(session, KNOWN["season_id"][2017], 1)
    assert data is not None
    # Four perspective rows for 2017 wk1 fold into two game cards.
    assert len(data["games"]) == 2
    assert data["is_scored"] is True


def test_week_matchups_card_has_winner_and_margin(session: Session) -> None:
    data = week_matchups(session, KNOWN["season_id"][2017], 1)
    assert data is not None
    ice_id = KNOWN["team_id"][(2017, "ice")]
    card = next(
        g for g in data["games"] if ice_id in {g["team_a"]["team_id"], g["team_b"]["team_id"]}
    )
    assert card["winner_team_id"] == ice_id
    assert card["margin"] == 5.0  # 130 - 125
    winner = next(t for t in (card["team_a"], card["team_b"]) if t["team_id"] == ice_id)
    assert winner["is_winner"] is True


def test_week_matchups_unknown_season_returns_none(session: Session) -> None:
    assert week_matchups(session, 999999, 1) is None
