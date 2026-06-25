"""ADP market axis (reach / value) — blend math + draft surface wiring."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ff_dashboard.analytics.adp import blend_player_adp, market_axis
from ff_dashboard.analytics.draft import draft_board, draft_tendencies, draft_value
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _row(
    source: str, adp: float, *, fallback: bool = False, fmt: str = "full_ppr"
) -> SimpleNamespace:
    return SimpleNamespace(source=source, adp=adp, actual_format=fmt, format_fallback=fallback)


# --- Blend (pure, no DB) ---------------------------------------------------


def test_blend_weights_two_sources() -> None:
    blend = blend_player_adp([_row("ffc", 8.0), _row("mfl", 9.0)])
    assert blend is not None
    # (0.5*8 + 0.3*9) / 0.8 = 8.375 → 8.4
    assert blend["adp"] == 8.4
    assert blend["adp_sources"] == ["ffc", "mfl"]
    assert blend["adp_source_spread"] == 1.0
    assert blend["adp_format"] == "full_ppr"  # FFC is the dominant (highest-weight) source


def test_blend_renormalizes_over_present_sources() -> None:
    # A single source blends to itself, not a penalized fraction of its weight.
    blend = blend_player_adp([_row("ffc", 5.0)])
    assert blend is not None
    assert blend["adp"] == 5.0
    assert blend["adp_source_spread"] == 0.0


def test_blend_surfaces_dominant_format_fallback() -> None:
    blend = blend_player_adp([_row("ffc", 3.0, fallback=True, fmt="standard")])
    assert blend is not None
    assert blend["adp_format"] == "standard"
    assert blend["adp_format_fallback"] is True


def test_blend_none_when_no_usable_adp() -> None:
    assert blend_player_adp([]) is None
    assert blend_player_adp([SimpleNamespace(source="ffc", adp=None)]) is None


# --- Sign convention (pure) ------------------------------------------------


def test_market_axis_signs() -> None:
    # Drafted earlier than the market (overall 1 < adp 8) → reach (negative).
    reach = market_axis(8.4, 1)
    assert reach["adp_delta"] == -7.4
    assert reach["market_label"] == "reach"
    # Drafted later than the market (overall 4 > adp 1) → value (positive).
    value = market_axis(1.0, 4)
    assert value["adp_delta"] == 3.0
    assert value["market_label"] == "value"
    # On the nose → on_market.
    assert market_axis(2.0, 2)["market_label"] == "on_market"
    # No ADP → unavailable.
    assert market_axis(None, 5) == {"adp_delta": None, "market_label": None}


# --- Over the fixture DB ---------------------------------------------------


def _picks_by_overall(session: Session) -> dict[int, dict]:
    board = draft_board(session, KNOWN["season_id"][2016])
    assert board is not None and board["available"]
    return {p["overall"]: p for rnd in board["rounds"] for p in rnd["picks"]}


def test_board_picks_carry_market_axis(session: Session) -> None:
    picks = _picks_by_overall(session)

    # Kelce @ overall 1, blended ADP 8.4 across FFC+MFL → a reach.
    kelce = picks[1]
    assert kelce["adp_available"] is True
    assert kelce["market_label"] == "reach"
    assert kelce["adp_delta"] == -7.4
    assert set(kelce["adp_sources"]) == {"ffc", "mfl"}
    assert kelce["adp_source_spread"] == 1.0

    # McCaffrey @ overall 4, ADP 1.0 → a value.
    assert picks[4]["market_label"] == "value"
    assert picks[4]["adp_delta"] == 3.0

    # Jefferson @ overall 3 has no ADP row → an honest gap, not a zero.
    jjet = picks[3]
    assert jjet["adp_available"] is False
    assert jjet["adp"] is None
    assert jjet["adp_reason"] == "no_market_data"


def test_value_reaches_and_values_leaderboards(session: Session) -> None:
    value = draft_value(session, KNOWN["season_id"][2016])
    assert value is not None
    assert value["adp_definition"]
    assert "ffc" in value["adp_weights"]

    reach_overalls = [p["overall"] for p in value["reaches"]]
    value_overalls = [p["overall"] for p in value["values"]]
    assert 1 in reach_overalls  # Kelce reached
    assert 4 in value_overalls  # McCaffrey was a value
    # Reaches are negative-delta, values positive-delta — never crossed.
    assert all(p["adp_delta"] < 0 for p in value["reaches"])
    assert all(p["adp_delta"] > 0 for p in value["values"])


def test_value_not_captured_season_still_has_adp_shape(session: Session) -> None:
    value = draft_value(session, KNOWN["season_id"][2015])  # no captured draft
    assert value is not None
    assert value["available"] is False
    assert value["reaches"] == []
    assert value["values"] == []
    assert value["adp_definition"]


def test_draft_tendencies_aggregate(session: Session) -> None:
    tend = draft_tendencies(session)
    assert tend["available"] is True
    by_owner = {m["owner_name"]: m for m in tend["managers"]}
    # Every reported manager has at least one ADP-covered pick (honest denominator).
    assert all(m["n_picks_with_adp"] >= 1 for m in tend["managers"])
    # A manager who only reached shows reach_rate 1.0; one who only found value, value_rate 1.0.
    reachers = [m for m in tend["managers"] if m["reach_rate"] == 1.0]
    valuers = [m for m in tend["managers"] if m["value_rate"] == 1.0]
    assert reachers and valuers
    assert by_owner  # owners resolved to names
