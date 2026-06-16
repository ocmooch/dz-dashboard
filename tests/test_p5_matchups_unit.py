"""P5 — matchups & box-score unit tests against the fixture's known answers.

The optimal-lineup solver is checked to the decimal both as a standalone matroid
solver and end-to-end through the hand-authored Iceman 2017 wk1 box score.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from ff_dashboard.analytics.injuries import injury_fields
from ff_dashboard.analytics.matchups import (
    _roster_data_context_from_transactions,
    _score_context,
    box_score,
    classify_zero,
    roster_sort_key,
    slot_accepts,
    solve_optimal,
    week_matchups,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    import pytest
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
    # leaked into the optimal, the total would exceed 126.
    assert _ice_box(session)["optimal_total"] == 126.0


def test_box_dst_starter_is_scored(session: Session) -> None:
    # DST is scored end-to-end: the DEF starter carries real points, is available,
    # and is counted in the starter total (113.0 includes the 9.0 DST).
    home = _ice_box(session)
    dst = next(p for p in home["lineup"] if p["position"] == "DEF")
    assert dst["is_starter"] is True
    assert dst["league_points"] == KNOWN["box_dst_points"]  # 9.0, never a None gap
    assert dst["available"] is True
    assert dst["reason"] is None
    assert home["starter_points"] == KNOWN["box_starter_total"]  # 113.0, DST included


def test_box_def_starter_with_missing_row_is_flagged(session: Session) -> None:
    # A DEF starter whose scored row is genuinely absent still surfaces as a gap,
    # never a fake 0 — the per-row honesty survives DST being scored at large.
    # Goose is the away side of the Iceman 2017 wk1 matchup; its lone DST is unscored.
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = box_score(session, mid)
    assert data is not None
    dst = next(p for p in data["away"]["lineup"] if p["position"] == "DEF" and p["is_starter"])
    assert dst["league_points"] is None  # never 0
    assert dst["available"] is False
    assert dst["reason"] == "team_defense_not_scored"


def test_box_non_def_missing_row_is_did_not_play_zero(session: Session) -> None:
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = box_score(session, mid)
    assert data is not None
    row = next(p for p in data["away"]["lineup"] if p["player_name"] == "No Stat Bench Guy")
    assert row["available"] is True
    assert row["league_points"] == 0.0
    assert row["reason"] is None
    assert row["zero_reason"] == "did_not_play"
    assert row["context_label"] == "DNP"
    assert row["context_detail"] is not None
    assert "No injury designation" in row["context_detail"]


def test_box_uses_authoritative_nfl_com_points_for_unscored_player(session: Session) -> None:
    # A player nflverse never scored (no scored row) but with an authoritative
    # nfl_com_points shows that real value, available — never a "no scored data"
    # gap. This is the inactive / DNP / bye case that scores a legitimate value.
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = box_score(session, mid)
    assert data is not None
    viper = next(p for p in data["away"]["lineup"] if p["player_name"] == "Viper D/ST")
    assert viper["available"] is True
    assert viper["league_points"] == 7.0  # from extra_data.nfl_com_points, not nflverse
    assert viper["reason"] is None


# --- Zero-point context classification --------------------------------------


def test_classify_zero_only_fires_on_an_authoritative_zero() -> None:
    # A non-zero (or missing) score is never annotated.
    assert classify_zero(12.0, "@KC", 12.0) == (None, None)
    assert classify_zero(None, "Bye", None) == (None, None)


def test_classify_zero_bye() -> None:
    # The per-week opponent "Bye" means the player's NFL team did not play.
    assert classify_zero(0.0, "Bye", None) == ("bye", None)
    assert classify_zero(0.0, "bye", 0.0) == ("bye", None)  # case-insensitive, bye wins


def test_classify_zero_did_not_play() -> None:
    # Team played (a real opponent) but the player has no stat line at all.
    assert classify_zero(0.0, "@KC", None) == ("did_not_play", None)


def test_classify_zero_played_and_scored_nothing() -> None:
    # A real stat line that nets ~0: played, scored nothing → no annotation.
    assert classify_zero(0.0, "@KC", 0.0) == (None, None)
    assert classify_zero(0.0, "@KC", 0.4) == (None, None)  # sub-threshold, still a clean 0


def test_classify_zero_unexpected_carries_a_reason() -> None:
    # League scored 0 but nflverse credits material points → flagged, with a note.
    reason, detail = classify_zero(0.0, "@KC", 8.0)
    assert reason == "unexpected"
    assert detail is not None and "8" in detail


def test_box_zero_context_is_wired_end_to_end(session: Session) -> None:
    # The box score surfaces a bye 0 and an "unexpected" 0 (league 0 vs nflverse 8)
    # on the away lineup, where no KNOWN total is asserted.
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = box_score(session, mid)
    assert data is not None
    away = data["away"]["lineup"]

    bye = next(p for p in away if p["player_name"] == "Bye Week Guy")
    assert bye["available"] is True
    assert bye["league_points"] == 0.0
    assert bye["zero_reason"] == "bye"
    assert bye["context_label"] == "Bye"

    mismatch = next(p for p in away if p["player_name"] == "Mismatch Guy")
    assert mismatch["league_points"] == 0.0  # authoritative league value, not nflverse 8.0
    assert mismatch["zero_reason"] == "unexpected"
    assert mismatch["zero_detail"] is not None
    assert mismatch["context_label"] == "Check"


def test_box_reserve_points_are_explained(session: Session) -> None:
    home = _ice_box(session)
    row = next(p for p in home["lineup"] if p["player_name"] == "Ice IR Guy")
    assert row["roster_slot"] == "IR"
    assert row["league_points"] == 30.0
    assert row["context_label"] == "RES"
    assert row["context_detail"] is not None
    assert "does not prove why" in row["context_detail"]
    assert row["reserve_eligibility_status"] == "IR"


def test_box_flags_roster_before_team_acquisition_as_data_drift() -> None:
    context = _roster_data_context_from_transactions(
        [
            SimpleNamespace(
                transaction_type="free_agent_add",
                effective_week=3,
                team_id=10,
                direction="in",
                extra_data=None,
            )
        ],
        team_id=10,
        week=1,
        roster_slot="BN",
    )
    assert context is not None
    assert context[0] == "DATA"
    assert "first add him in W3" in context[1]


def test_box_flags_slot_transaction_snapshot_conflict() -> None:
    context = _roster_data_context_from_transactions(
        [
            SimpleNamespace(
                transaction_type="lineup_change",
                effective_week=1,
                team_id=None,
                direction="out",
                extra_data={"from_slot": "BN", "to_slot": "WR"},
            )
        ],
        team_id=10,
        week=1,
        roster_slot="RES",
    )
    assert context is not None
    assert context[0] == "DATA"
    assert "transaction moved him to WR" in context[1]


def test_box_slot_conflict_detail_dedupes_repeated_target_slots() -> None:
    # Several same-week lineup_change rows can repeat the same to_slot; the detail
    # must not read "BN/R/W/T/BN/R/W/T" — duplicates are collapsed, order kept.
    txns = [
        SimpleNamespace(
            transaction_type="lineup_change",
            effective_week=1,
            team_id=None,
            direction="out",
            extra_data={"from_slot": "RB", "to_slot": slot},
        )
        for slot in ("BN", "R/W/T", "BN", "R/W/T")
    ]
    context = _roster_data_context_from_transactions(txns, team_id=10, week=1, roster_slot="RB")
    assert context is not None
    assert context[0] == "DATA"
    assert "moved him to BN/R/W/T," in context[1]
    assert "BN/R/W/T/BN" not in context[1]


def test_reserve_slot_with_points_is_never_labeled_injured() -> None:
    # A reserve-slot player credited with points clearly played and scored; an
    # injury-report row for that week must not turn the badge into "INJ" — that
    # would imply an injury the data doesn't prove (see Nabers/Hunter on m193).
    injury = SimpleNamespace(
        report_status="Questionable",
        report_primary_injury="Knee",
        report_secondary_injury=None,
        practice_status="Did Not Participate In Practice",
    )
    label, detail = _score_context(
        data_context=None,
        league_points=12.1,
        zero_reason=None,
        zero_detail=None,
        nfl_opponent="DAL",
        nfl_game_status="Win,24-20",
        roster_slot="RES",
        roster_status=None,
        roster_status_label=None,
        reserve_eligibility_status="Questionable",
        injury_payload=injury_fields(injury),
        player_played=True,
    )
    assert label == "RES"
    assert detail is not None
    assert "does not prove why" in detail


def _score_context_kwargs(**overrides: object) -> dict[str, object]:
    """Minimal ``_score_context`` arguments with sane defaults, for badge tests."""
    base: dict[str, object] = {
        "data_context": None,
        "league_points": 14.0,
        "zero_reason": None,
        "zero_detail": None,
        "nfl_opponent": "DAL",
        "nfl_game_status": "Win,24-20",
        "roster_slot": "WR",
        "roster_status": None,
        "roster_status_label": None,
        "reserve_eligibility_status": None,
        "injury_payload": injury_fields(None),
        "player_played": True,
    }
    base.update(overrides)
    return base


def test_score_context_suppresses_incompatible_status_when_played() -> None:
    # NFL.com current-state drift: an "Inactive" stamped onto a week the player
    # actually scored must not surface as a badge.
    label, detail = _score_context(
        **_score_context_kwargs(
            roster_status="IA",
            roster_status_label="Inactive",
            league_points=20.0,
            player_played=True,
        )
    )
    assert label is None
    assert detail is None


def test_score_context_suppresses_injured_reserve_when_played() -> None:
    label, _ = _score_context(
        **_score_context_kwargs(
            roster_status="IR",
            roster_status_label="Injured Reserve",
            player_played=True,
        )
    )
    assert label is None


def test_score_context_keeps_questionable_when_played() -> None:
    # A game-time injury designation is compatible with playing — keep it.
    label, detail = _score_context(
        **_score_context_kwargs(
            roster_status="Q",
            roster_status_label="Questionable",
            player_played=True,
        )
    )
    assert label == "Q"
    assert detail == "Questionable"


def test_score_context_keeps_incompatible_status_when_did_not_play() -> None:
    # An inactive player who genuinely did not play keeps the badge: it is the
    # honest explanation of the 0, not drift.
    label, _ = _score_context(
        **_score_context_kwargs(
            league_points=0.0,
            zero_reason="did_not_play",
            roster_status="IA",
            roster_status_label="Inactive",
            player_played=False,
        )
    )
    assert label == "IA"


def test_box_lineup_is_in_canonical_display_order(session: Session) -> None:
    # Starters read QB, RB, RB, WR, WR, TE, FLEX, K, DST; then bench (by
    # position); then IR last — regardless of the order rows came out of the DB.
    home = _ice_box(session)
    order = [(p["roster_slot"], p["position"]) for p in home["lineup"]]
    assert order == [
        ("QB", "QB"),
        ("RB", "RB"),
        ("RB", "RB"),
        ("WR", "WR"),
        ("WR", "WR"),
        ("TE", "TE"),
        ("FLEX", "WR"),
        ("K", "K"),
        ("DEF", "DEF"),
        ("BN", "QB"),  # bench, ordered by position
        ("BN", "RB"),
        ("BN", "WR"),
        ("IR", "RB"),  # IR always last
    ]


def test_roster_sort_key_groups_and_orders() -> None:
    # The FLEX sorts just after TE no matter who fills it.
    assert roster_sort_key("R/W/T", "WR") == (0, 4)
    assert roster_sort_key("TE", "TE") < roster_sort_key("R/W/T", "RB")
    # Bench after every starter; IR after every bench player.
    assert roster_sort_key("QB", "QB") < roster_sort_key("BN", "QB")
    assert roster_sort_key("BN", "WR") < roster_sort_key("IR", "RB")
    # Within the bench, position drives the order.
    assert roster_sort_key("BN", "QB") < roster_sort_key("BN", "DEF")


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


def test_box_clean_data_emits_no_integrity_warning(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # The cross-team / cross-season integrity alarms must not false-positive on a
    # clean matchup: a healthy box score logs nothing at WARNING.
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    with caplog.at_level(logging.WARNING, logger="ff_dashboard.analytics.matchups"):
        box_score(session, mid)
    assert caplog.records == []


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
