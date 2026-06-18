"""Unit tests for the reusable weighting primitive (pure, no DB)."""

from __future__ import annotations

from ff_dashboard.analytics.weighting import positional_weight, weighted_impact

# --- weighted_impact --------------------------------------------------------


def test_weighted_impact_identity_returns_base() -> None:
    assert weighted_impact(12.5) == 12.5
    assert weighted_impact(-8.0, cost_weight=1.0, opportunity_weight=1.0) == -8.0


def test_weighted_impact_multiplies_all_three() -> None:
    assert weighted_impact(10.0, cost_weight=0.5, opportunity_weight=1.5) == 7.5


def test_weighted_impact_preserves_sign() -> None:
    # Weights are >= 0, so the sign of the result always matches the base.
    assert weighted_impact(-4.0, cost_weight=2.0, opportunity_weight=1.5) < 0
    assert weighted_impact(4.0, cost_weight=2.0, opportunity_weight=1.5) > 0


def test_weighted_impact_zero_base_is_zero() -> None:
    assert weighted_impact(0.0, cost_weight=2.0, opportunity_weight=3.0) == 0.0


# --- positional_weight ------------------------------------------------------


def test_positional_weight_endpoints() -> None:
    # Decreasing: first position is full weight, last decays to the floor.
    assert positional_weight(1, 10, floor=0.3) == 1.0
    assert round(positional_weight(10, 10, floor=0.3), 6) == 0.3


def test_positional_weight_monotonic_decreasing() -> None:
    weights = [positional_weight(p, 12, floor=0.3) for p in range(1, 13)]
    assert weights == sorted(weights, reverse=True)
    assert len(set(weights)) == 12  # strictly decreasing, no ties


def test_positional_weight_invert_mirrors() -> None:
    # The steal curve: the last position is the heavy one.
    assert round(positional_weight(1, 10, floor=0.3, invert=True), 6) == 0.3
    assert positional_weight(10, 10, floor=0.3, invert=True) == 1.0
    # invert(position) == decreasing(span - position + 1) — a true mirror.
    span, floor = 10, 0.3
    for p in range(1, span + 1):
        mirror = positional_weight(span - p + 1, span, floor=floor)
        assert round(positional_weight(p, span, floor=floor, invert=True), 9) == round(mirror, 9)


def test_positional_weight_curve_keeps_endpoints_bends_middle() -> None:
    # A steeper curve front-loads the decay but never moves the endpoints.
    linear = positional_weight(5, 10, floor=0.2, curve=1.0)
    steep = positional_weight(5, 10, floor=0.2, curve=2.0)
    assert steep < linear  # mid-pick decays faster under a steeper curve
    assert positional_weight(1, 10, floor=0.2, curve=2.0) == 1.0
    assert round(positional_weight(10, 10, floor=0.2, curve=2.0), 6) == 0.2


def test_positional_weight_degenerate_span() -> None:
    # A single-pick draft (or span <= 1) has no spread → full weight.
    assert positional_weight(1, 1, floor=0.3) == 1.0
    assert positional_weight(1, 0, floor=0.3, invert=True) == 1.0
