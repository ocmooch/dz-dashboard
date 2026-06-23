"""Reusable weighting primitive — a signed base metric scaled by a draft-cost
weight and an opportunity factor (``base * cost * opportunity``).

Pure functions: no FastAPI, no DB. The draft impact model
(:mod:`ff_dashboard.analytics.draft`) is the first caller, but the same shape —
a base metric scaled by how "expensive" a thing was and how it had to be carried
— is expected to recur elsewhere on the dashboard, so the multiply and the
monotonic position weight live here rather than buried in one feature.
"""

from __future__ import annotations


def weighted_impact(
    base: float,
    *,
    cost_weight: float = 1.0,
    opportunity_weight: float = 1.0,
) -> float:
    """Scale a signed ``base`` metric by two non-negative weights.

    Multiplicative by design: the unit of ``base`` is preserved (the result is a
    re-scaled magnitude, not a unitless score), and the sign is automatic —
    ``sign(result) == sign(base)`` because the weights are ``>= 0``. Identity
    weights (both ``1.0``) return ``base`` unchanged.
    """
    return base * cost_weight * opportunity_weight


def positional_weight(
    position: int,
    span: int,
    *,
    floor: float = 0.0,
    curve: float = 1.0,
    invert: bool = False,
) -> float:
    """Monotonic weight in ``[floor, 1.0]`` over an ordered ``position`` in ``1..span``.

    Decreasing by default: ``position == 1`` returns ``1.0`` and
    ``position == span`` returns ``floor``, with ``curve`` shaping the decay
    (``1.0`` linear, ``>1`` front-loaded). ``invert=True`` mirrors the curve so
    the *last* position carries the weight (the steal curve: a late pick weighs
    like an early one). A degenerate span (``span <= 1``) has no spread, so it
    always weighs ``1.0``.
    """
    if span <= 1:
        return 1.0
    # r in [0, 1]: 0 at the first position, 1 at the last.
    r = (position - 1) / (span - 1)
    r = min(max(r, 0.0), 1.0)
    if invert:
        r = 1.0 - r
    weight: float = floor + (1.0 - floor) * (1.0 - r) ** curve
    return weight
