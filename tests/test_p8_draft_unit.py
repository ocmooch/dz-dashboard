"""P8 — draft analytics unit tests against hand-computed known answers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ff_dashboard.analytics.draft import (
    FANTASY_POSITIONS,
    IMPACT_DEFINITION,
    VALUE_SLOT_WINDOW,
    _classify_pick_scoring,
    _clean_rounded,
    _did_not_play_detail,
    _expected_by_slot,
    _pick_impact,
    _resolved_cluster_points,
    best_worst_picks,
    draft_board,
    draft_value,
    fantasy_position,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --- NFL → fantasy position folding (no DB) --------------------------------


def test_fantasy_position_folds_onto_the_league_universe() -> None:
    # Skill positions pass through unchanged.
    for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
        assert fantasy_position(pos) == pos
    # Aliases / no-fantasy-slot positions fold to their clear fantasy home.
    assert fantasy_position("FB") == "RB"  # fullback plays RB
    assert fantasy_position("PK") == "K"
    assert fantasy_position("DST") == "DEF"
    assert fantasy_position("D/ST") == "DEF"
    # A two-way player listed at a defensive position folds to his offensive role
    # (Travis Hunter, listed CB, drafted and scored as a receiver).
    assert fantasy_position("CB") == "WR"
    # Every fold lands inside the fantasy universe.
    for pos in ("FB", "PK", "DST", "CB"):
        assert fantasy_position(pos) in FANTASY_POSITIONS


def test_fantasy_position_is_normalized_and_honest_about_unknowns() -> None:
    assert fantasy_position("wr") == "WR"
    assert fantasy_position(" QB ") == "QB"
    # A position with no fantasy home is left unmapped rather than guessed, so it
    # stays out of the filter and the impact model.
    assert fantasy_position("LB") is None
    assert fantasy_position(None) is None


# --- The pure pick-scoring classifier (no DB) ------------------------------


def _player(position: str = "WR", gsis_id: str | None = "00-0000001") -> SimpleNamespace:
    return SimpleNamespace(position=position, gsis_id=gsis_id)


def test_classify_scored_pick_passes_through() -> None:
    out = _classify_pick_scoring(
        player=_player(),
        scored_points=123.456,
        season_is_scored=True,
        played=True,
        roster_slots={"WR"},
    )
    assert out["season_points"] == 123.46  # rounded
    assert out["available"] is True
    assert out["reason"] is None
    assert out["zero_reason"] is None


def test_classify_unscored_season_is_a_gap() -> None:
    out = _classify_pick_scoring(
        player=_player(),
        scored_points=None,
        season_is_scored=False,
        played=False,
        roster_slots=set(),
    )
    assert out["season_points"] is None
    assert out["available"] is False
    assert out["reason"] == "season_unscored"


def test_classify_defense_without_stats_is_always_a_gap() -> None:
    # A DST can never have a legitimate season-long 0 — even with a raw line it
    # is a scoring gap, never a real zero, so DEF takes precedence over "played".
    out = _classify_pick_scoring(
        player=_player(position="DEF", gsis_id=None),
        scored_points=None,
        season_is_scored=True,
        played=True,
        roster_slots={"DEF"},
    )
    assert out["season_points"] is None
    assert out["available"] is False
    assert out["reason"] == "team_defense_not_scored"
    assert out["zero_reason"] is None


def test_classify_played_but_unscored_is_a_gap() -> None:
    out = _classify_pick_scoring(
        player=_player(),
        scored_points=None,
        season_is_scored=True,
        played=True,
        roster_slots={"WR"},
    )
    assert out["reason"] == "player_unscored"
    assert out["available"] is False


def test_classify_never_played_weak_identity_is_unresolved() -> None:
    for gsis in (None, "", "   "):
        out = _classify_pick_scoring(
            player=_player(gsis_id=gsis),
            scored_points=None,
            season_is_scored=True,
            played=False,
            roster_slots={"BN"},
        )
        assert out["reason"] == "player_identity_unresolved"
        assert out["available"] is False


def test_classify_never_played_real_player_is_a_genuine_zero() -> None:
    # Drafted, fully identified, scored season, no game stats all year (a torn
    # ACL in camp): a real 0.0 the board shows with a note, not a hidden gap.
    out = _classify_pick_scoring(
        player=_player(gsis_id="00-0032054"),
        scored_points=None,
        season_is_scored=True,
        played=False,
        roster_slots={"BN"},
    )
    assert out["season_points"] == 0.0
    assert out["available"] is True
    assert out["reason"] is None
    assert out["zero_reason"] == "did_not_play_season"
    assert "active bench" in (out["zero_detail"] or "")


def test_did_not_play_detail_distinguishes_reserve_from_bench() -> None:
    assert "reserve / IR" in _did_not_play_detail({"RES"})
    assert "active bench" in _did_not_play_detail({"BN"})
    # No roster rows after the draft → just the base note, no carry phrasing.
    base = _did_not_play_detail(set())
    assert "reserve / IR" not in base and "active bench" not in base


# --- The pure expectation helper (no DB) -----------------------------------


def test_expected_by_slot_windows_neighbours() -> None:
    # Two seasons' worth of picks at overalls 1..4; early slots score more, so
    # the windowed mean rises toward the top of the draft — the intended shape.
    history = [
        (1, 60.0),
        (2, 50.0),
        (3, 40.0),
        (4, 30.0),
        (1, 58.0),
        (2, 52.0),
        (3, 38.0),
        (4, 32.0),
    ]
    expected = _expected_by_slot(history)
    # slot 1 pools overalls within ±2 → {1,2,3}: (60+58+50+52+40+38)/6 = 49.6667
    assert round(expected[1], 4) == 49.6667
    # slot 4 pools {2,3,4}: (50+52+40+38+30+32)/6 = 40.3333
    assert round(expected[4], 4) == 40.3333
    # higher (better) slot has the higher expectation
    assert expected[1] > expected[4]


def test_expected_by_slot_empty() -> None:
    assert _expected_by_slot([]) == {}
    assert VALUE_SLOT_WINDOW == 2


def test_value_rounding_normalizes_negative_zero() -> None:
    assert _clean_rounded(83.3 - 83.30425) == 0.0
    assert str(_clean_rounded(83.3 - 83.30425)) == "0.0"


def test_identity_cluster_points_prefer_drafted_id_without_double_counting() -> None:
    rows = [
        (1032, 1, 10.0),
        (25239, 1, 11.0),  # duplicate source member: canonical row wins
        (25239, 2, 20.0),  # member-only week fills the canonical player's total
    ]
    assert _resolved_cluster_points(rows, {1032: [1032, 25239]}, 2) == {1032: 30.0}


# --- The pure composite impact scorer (no DB) ------------------------------


def test_impact_none_iff_value_none() -> None:
    out = _pick_impact(value=None, overall=1, total_picks=12, reg_weeks=14, carry=None)
    assert out["impact"] is None
    assert out["impact_components"] is None


def test_impact_draft_cost_amplifies_early_busts_and_late_steals() -> None:
    early_bust = _pick_impact(value=-10.0, overall=1, total_picks=12, reg_weeks=14, carry=None)
    late_bust = _pick_impact(value=-10.0, overall=12, total_picks=12, reg_weeks=14, carry=None)
    # Same deficit, but wasting an early pick hurts more.
    assert early_bust["impact"] < late_bust["impact"] < 0

    early_steal = _pick_impact(value=10.0, overall=1, total_picks=12, reg_weeks=14, carry=None)
    late_steal = _pick_impact(value=10.0, overall=12, total_picks=12, reg_weeks=14, carry=None)
    # Same surplus, but a late-round steal is the bigger coup.
    assert late_steal["impact"] > early_steal["impact"] > 0


def test_impact_opportunity_applies_to_busts_only() -> None:
    # A steal that produced never wasted its slot — no opportunity penalty even
    # when it sat on the bench for weeks.
    steal = _pick_impact(
        value=8.0,
        overall=6,
        total_picks=12,
        reg_weeks=14,
        carry={"bench": 14, "ir": 0, "weeks": 14},
    )
    assert steal["impact_components"]["opportunity_weight"] == 1.0
    assert steal["impact_components"]["bench_weeks"] == 14  # still reported, just not applied


def test_impact_bench_carry_costs_more_than_ir_than_dropped() -> None:
    common = {"value": -8.0, "overall": 3, "total_picks": 12, "reg_weeks": 14}
    bench = _pick_impact(**common, carry={"bench": 11, "ir": 0, "weeks": 11})
    ir = _pick_impact(**common, carry={"bench": 0, "ir": 14, "weeks": 14})
    dropped = _pick_impact(**common, carry=None)
    # Same value and slot → carrying it on the active bench is the most expensive
    # bust, IR cheaper, and a dropped/never-rostered bust cheapest.
    assert bench["impact"] < ir["impact"] < dropped["impact"] < 0
    assert dropped["impact_components"]["opportunity_weight"] == 1.0


def test_impact_degrades_honestly_when_roster_history_missing() -> None:
    # No roster rows → opportunity is unknown, not zero: the weight defaults to
    # 1.0 and impact is exactly value * cost_weight (never fabricated).
    out = _pick_impact(value=-12.0, overall=4, total_picks=12, reg_weeks=14, carry=None)
    c = out["impact_components"]
    assert c["opportunity_available"] is False
    assert c["opportunity_weight"] == 1.0
    assert out["impact"] == round(-12.0 * c["cost_weight"], 2)
    assert out["impact"] is not None  # honest degrade, not a null


def test_impact_motivating_case_cruz_outranks_gordon() -> None:
    # Equal value and slot: 2015 Cruz (11 weeks on the active bench) is a more
    # expensive bust than 2016 Gordon (a full season stashed on IR / reserve).
    cruz = _pick_impact(
        value=-40.0,
        overall=24,
        total_picks=120,
        reg_weeks=14,
        carry={"bench": 11, "ir": 0, "weeks": 11},
    )
    gordon = _pick_impact(
        value=-40.0,
        overall=24,
        total_picks=120,
        reg_weeks=14,
        carry={"bench": 0, "ir": 14, "weeks": 14},
    )
    assert cruz["impact"] < gordon["impact"] < 0


def test_impact_uses_position_normalized_value_and_excludes_defense() -> None:
    weighted = _pick_impact(
        value=110.0,
        overall=100,
        total_picks=180,
        reg_weeks=14,
        carry=None,
        position_mean=70.0,
        position_stddev=20.0,
    )
    assert weighted["impact_components"]["normalized_value"] == 2.0
    assert weighted["impact"] != 110.0

    defense = _pick_impact(
        value=60.0,
        overall=170,
        total_picks=180,
        reg_weeks=14,
        carry=None,
        weighted_eligible=False,
    )
    assert defense["impact"] is None
    assert defense["impact_components"]["weighted_reason"] == "position_not_weighted"


# --- Board over the fixture ------------------------------------------------


def test_board_orders_picks_and_resolves_players(session: Session) -> None:
    board = draft_board(session, KNOWN["season_id"][2016])
    assert board is not None
    assert board["available"] is True
    assert board["num_teams"] == 4
    # Four teams, four picks → a single round.
    assert [r["round"] for r in board["rounds"]] == [1]
    picks = board["rounds"][0]["picks"]
    assert [p["overall"] for p in picks] == [1, 2, 3, 4]
    assert [p["pick_in_round"] for p in picks] == [1, 2, 3, 4]
    pid = KNOWN["player_id"]
    assert [p["player_id"] for p in picks] == [
        pid["kelce"],
        pid["lamar"],
        pid["jjet"],
        pid["cmc"],
    ]
    # McCaffrey was Maverick's rostered draftee — board and roster agree.
    cmc = picks[-1]
    assert cmc["owner_name"] == "Maverick"
    assert cmc["season_points"] == 55.0


def test_board_gap_when_no_draft_captured(session: Session) -> None:
    # 2015 is unscored AND has no draft transactions → the honest gap, not zeros.
    board = draft_board(session, KNOWN["season_id"][2015])
    assert board is not None
    assert board["available"] is False
    assert board["reason"] == "draft_not_captured"
    assert board["rounds"] == []
    # 2017 is scored but its draft was likewise not captured.
    board17 = draft_board(session, KNOWN["season_id"][2017])
    assert board17 is not None
    assert board17["available"] is False


def test_board_unknown_season_is_none(session: Session) -> None:
    assert draft_board(session, 99999) is None


# --- Value (steals / busts) ------------------------------------------------


def test_value_identifies_steal_and_bust(session: Session) -> None:
    value = draft_value(session, KNOWN["season_id"][2016])
    assert value is not None
    assert value["available"] is True
    assert value["slot_window"] == VALUE_SLOT_WINDOW
    assert "regular-season fantasy points" in value["definition"]

    steal = value["steals"][0]
    assert steal["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert steal["overall"] == KNOWN["draft_top_steal"]["overall"]
    assert steal["value"] == KNOWN["draft_top_steal"]["value"]  # 8.33

    bust = value["busts"][0]
    assert bust["player_name"] == KNOWN["draft_top_bust"]["player"]
    assert bust["overall"] == KNOWN["draft_top_bust"]["overall"]
    assert bust["value"] == KNOWN["draft_top_bust"]["value"]  # -13.67

    # Full pick list is sorted by value, highest first.
    values = [p["value"] for p in value["picks"]]
    assert values == sorted(values, reverse=True)


def test_value_carries_composite_impact(session: Session) -> None:
    value = draft_value(session, KNOWN["season_id"][2016])
    assert value is not None
    # The composite is exposed alongside the honest per-slot value.
    assert value["impact_definition"] == IMPACT_DEFINITION
    assert value["weights"]["opp_bench_weight"] == 1.0
    assert value["weights"]["cost_floor"] == 0.30

    # Every scored pick carries an impact + a legible component breakdown.
    for p in value["picks"]:
        if p["value"] is None:
            assert p["impact"] is None
        else:
            assert p["impact"] is not None
            comp = p["impact_components"]
            assert comp["base_value"] == p["value"]
            assert 0.0 <= comp["cost_weight"] <= 1.0

    # Steals are ranked by descending impact, busts by ascending impact.
    steal_impacts = [p["impact"] for p in value["steals"]]
    bust_impacts = [p["impact"] for p in value["busts"]]
    assert steal_impacts == sorted(steal_impacts, reverse=True)
    assert bust_impacts == sorted(bust_impacts)
    # The fixture's headline steal/bust sit at the extreme slots, so impact keeps
    # them on top: McCaffrey (last pick) the steal, Kelce (first pick) the bust.
    assert value["steals"][0]["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert value["busts"][0]["player_name"] == KNOWN["draft_top_bust"]["player"]


# --- Records book best/worst ever ------------------------------------------


def test_best_worst_picks_ever(session: Session) -> None:
    rec = best_worst_picks(session)
    assert rec["available"] is True
    assert rec["best_picks"][0]["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert rec["worst_picks"][0]["player_name"] == KNOWN["draft_top_bust"]["player"]
