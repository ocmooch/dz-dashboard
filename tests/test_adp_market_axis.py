"""ADP market axis (reach / value) — blend math + draft surface wiring."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ff_dashboard.analytics.adp import (
    adp_coverage,
    blend_player_adp,
    market_axis,
    on_market_cushion,
)
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


# --- Depth-scaled cushion (pure) -------------------------------------------


def test_on_market_cushion() -> None:
    # Floored at 4 near the top (2.5·√adp < 4 below ≈adp 2.56), slope beyond.
    assert on_market_cushion(1.0) == 4.0  # floored
    assert on_market_cushion(2.0) == 4.0  # floored
    assert on_market_cushion(4.0) == 5.0  # 2.5 · 2
    assert on_market_cushion(100.0) == 25.0  # 2.5 · 10
    # Monotonic non-decreasing in ADP.
    cushions = [on_market_cushion(a) for a in (1, 2, 4, 12, 36, 100, 150)]
    assert cushions == sorted(cushions)


def test_market_axis_depth_scaled_cushion() -> None:
    # Bijan 2025: blended ADP ≈4.1, taken 1st → Δ -3.1 sits inside the 5.06 cushion.
    assert market_axis(4.1, 1)["market_label"] == "on_market"
    # …but falling to 11 → Δ +6.9 clears it → a genuine value.
    assert market_axis(4.1, 11)["market_label"] == "value"
    # Consensus #1: a pick-5 grab is preference (cushion 4.0); pick 6 tips to value.
    assert market_axis(1.0, 5)["market_label"] == "on_market"
    assert market_axis(1.0, 6)["market_label"] == "value"
    # A deep player taken way early is still a clear reach (Δ -75 past cushion ≈28.5).
    assert market_axis(130.0, 55)["market_label"] == "reach"
    # On the nose → on_market.
    assert market_axis(2.0, 2)["market_label"] == "on_market"
    # The recalibration does NOT silence a genuine top-of-draft reach.
    reach = market_axis(8.4, 1)
    assert reach["adp_delta"] == -7.4
    assert reach["market_label"] == "reach"
    # The number stays the literal pick gap, independent of the label: Δ 3 is real,
    # but inside the floor-4 cushion it reads on_market (was "value" under the ±1 band).
    on_market = market_axis(1.0, 4)
    assert on_market["adp_delta"] == 3.0
    assert on_market["market_label"] == "on_market"
    # No ADP → unavailable.
    assert market_axis(None, 5) == {"adp_delta": None, "market_label": None}


def test_adp_coverage_flag() -> None:
    # FFC present → full coverage, no note.
    full = adp_coverage({1: {"adp_sources": ["ffc", "mfl"]}})
    assert full["limited"] is False
    assert full["sources"] == ["ffc", "mfl"]
    assert full["note"] is None
    # FFC absent (the 2025 case) → limited, with the honesty note and real sources.
    limited = adp_coverage({1: {"adp_sources": ["mfl", "sleeper"]}, 2: {"adp_sources": ["mfl"]}})
    assert limited["limited"] is True
    assert limited["sources"] == ["mfl", "sleeper"]
    assert limited["note"] is not None and "less precise" in limited["note"]
    # No ADP at all → nothing to qualify, not "limited", no note.
    empty = adp_coverage({})
    assert empty["limited"] is False
    assert empty["note"] is None


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

    # McCaffrey @ overall 4, ADP 1.0 → Δ +3.0, inside the floor-4 cushion → on_market.
    # The depth-scaled band protects the consensus elite from a 3-slot "value"
    # (under the old ±1 band this read "value"; the number is unchanged).
    assert picks[4]["market_label"] == "on_market"
    assert picks[4]["adp_delta"] == 3.0

    # Jefferson @ overall 3 has no ADP row → an honest gap, not a zero.
    jjet = picks[3]
    assert jjet["adp_available"] is False
    assert jjet["adp"] is None
    assert jjet["adp_reason"] == "no_market_data"


def test_board_carries_adp_coverage(session: Session) -> None:
    board = draft_board(session, KNOWN["season_id"][2016])
    assert board is not None and board["available"]
    # 2016 blends FFC (Kelce has FFC+MFL rows) → full coverage, no limited note.
    cov = board["adp_coverage"]
    assert cov["limited"] is False
    assert "ffc" in cov["sources"]
    assert cov["note"] is None


def test_value_reaches_and_values_leaderboards(session: Session) -> None:
    value = draft_value(session, KNOWN["season_id"][2016])
    assert value is not None
    assert value["adp_definition"]
    assert "ffc" in value["adp_weights"]

    reach_overalls = [p["overall"] for p in value["reaches"]]
    value_overalls = [p["overall"] for p in value["values"]]
    assert 1 in reach_overalls  # Kelce reached (Δ -7.4 clears its 7.25 cushion)
    # McCaffrey @4 (Δ +3.0) now sits inside its cushion → on_market, so it must NOT
    # leak into either leaderboard as a tiny "value" or "reach".
    assert 4 not in value_overalls
    assert 4 not in reach_overalls
    # Membership keys off the label (not a bare delta sign): every listed pick is a
    # genuine reach/value, negative/positive delta respectively, never crossed.
    assert all(p["market_label"] == "reach" and p["adp_delta"] < 0 for p in value["reaches"])
    assert all(p["market_label"] == "value" and p["adp_delta"] > 0 for p in value["values"])
    # 2016 blends FFC → full coverage.
    assert value["adp_coverage"]["limited"] is False


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
    # A manager who only truly reached still reads high (Iceman: Kelce Δ -7.4).
    reachers = [m for m in tend["managers"] if m["reach_rate"] == 1.0]
    assert reachers
    # Regression: Maverick's lone McCaffrey "value" (Δ +3.0) sat inside its cushion
    # under the depth-scaled band, so his value_rate drops to 0 — the ±1-era false
    # positive is gone. (His pick still counts toward the honest ADP denominator.)
    mav = by_owner.get("Maverick")
    assert mav is not None
    assert mav["n_picks_with_adp"] == 1
    assert mav["value_rate"] == 0.0
    assert by_owner  # owners resolved to names
