"""ADP blend + the market (reach / value) axis (``analytics/adp.py``).

The draft surfaces already score the **outcome** axis (did a pick pan out —
``value`` / ``impact``). This module adds the orthogonal **market** axis: where
the consensus drafted a player vs where this league actually did.

Phase 1 stores raw, source-faithful ADP rows (FFC / MFL / Sleeper) in
``player_adp``; the *blend* is deliberately kept here so the weighting stays a
tunable, documented knob rather than something baked into storage. For each
player we take a weighted mean across whichever sources have a row that season
(weights renormalized over the present sources, so an FFC-only early season isn't
penalized), and expose the cross-source spread as a *consensus* signal — a wide
spread means the market disagreed, so the reach/value read is softer.

Sign convention, fixed once: ``adp_delta = overall - composite_adp``.
**Positive ⇒ drafted later than the market (``overall`` is a higher pick number
than ADP) ⇒ value/bargain; negative ⇒ drafted earlier ⇒ reach.** A small
dead-band reads as "on market".
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.queries import player_adp_rows_for_season

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ff_dashboard.cache import AnalyticsCache

# Per-source blend weights — an *editable proposal* (echoed in the payload for
# transparency, like the draft impact weights). FFC is the most robust + the only
# team-count-aware source, so it leads; MFL has a known, trusted profile; Sleeper
# is modern-only (≈2018+) and absent earlier. Weights are renormalized over the
# sources actually present for a player, so a single-source season blends to that
# source alone rather than a penalized fraction.
ADP_SOURCE_WEIGHTS: dict[str, float] = {"ffc": 0.5, "mfl": 0.3, "sleeper": 0.2}

# On-market cushion: how many pick slots a draft can sit from the consensus and
# still read as "on market" rather than a reach or a value. The tolerance *grows
# with draft depth* — being 3 picks off in Round 1 is precise disagreement; being
# 3 picks off in Round 13 is rounding error — so the band is depth-scaled rather
# than flat: ``cushion(adp) = max(CUSHION_FLOOR, CUSHION_SLOPE * sqrt(adp))``.
# Two independent, documented knobs (echoed in the payload, like ADP_SOURCE_WEIGHTS):
#   * SLOPE — the ``sqrt(adp)`` term: tolerance starts tight at the top and widens
#     fast then flattens, mirroring how draft certainty decays. This *is* the
#     early/middle/late weighting; it falls out of the curve, no per-round rules.
#   * FLOOR — protects the consensus elite, where 1.01 vs 1.05 is pure preference.
#     Only bites below ≈ADP 2.6 (where ``2.5·√adp`` < 4); the mid/late curve is
#     untouched. Raise toward 5 to tolerate a bigger top grab; past ~5 it erodes
#     the falls-to-Round-2 value signal.
CUSHION_FLOOR = 4.0
CUSHION_SLOPE = 2.5

_WEIGHTS_PHRASE = ", ".join(f"{s.upper()} {w:g}" for s, w in ADP_SOURCE_WEIGHTS.items())

ADP_DEFINITION = (
    "ADP is the consensus average draft position blended across public sources "
    "(Fantasy Football Calculator, MyFantasyLeague, Sleeper), weighted "
    f"{_WEIGHTS_PHRASE} and matched to this league's format (full-PPR; half-PPR "
    "in 2010), 12-team. It is the closest public market to this league — not its "
    "own valuations. Reach / value is the gap between where the league drafted a "
    "player and the consensus, judged against a tolerance that grows with draft "
    "depth: a pick well earlier than its ADP is a reach, well later is a value, and "
    "anything inside the depth-scaled cushion reads as on-market. The cushion is "
    "tight at the top (where the elite tier is interchangeable and ordering is "
    "preference) and widens deeper into the draft (where exact slot matters less)."
)


def blend_player_adp(rows: list[Any]) -> dict[str, Any] | None:
    """Weighted-mean blend of one player's per-source ADP rows.

    ``rows`` are ``player_adp`` ORM rows (one per source). Returns the composite
    ADP plus provenance, or ``None`` when no row carries a usable ADP. Weights
    are renormalized over the sources actually present.
    """
    usable = [r for r in rows if getattr(r, "adp", None) is not None]
    if not usable:
        return None

    weighted_sum = 0.0
    weight_total = 0.0
    adps: list[float] = []
    sources: list[str] = []
    for row in usable:
        weight = ADP_SOURCE_WEIGHTS.get(row.source, 0.0)
        if weight <= 0:
            continue
        weighted_sum += weight * float(row.adp)
        weight_total += weight
        adps.append(float(row.adp))
        sources.append(row.source)

    if weight_total <= 0:  # only unknown-weight sources present — fall back to mean
        adps = [float(r.adp) for r in usable]
        sources = [r.source for r in usable]
        composite = sum(adps) / len(adps)
    else:
        composite = weighted_sum / weight_total

    # Format provenance: report the highest-weighted contributing source's row, so
    # a (loud) format fallback on the dominant source surfaces downstream.
    dominant = max(usable, key=lambda r: ADP_SOURCE_WEIGHTS.get(r.source, 0.0))
    return {
        "adp": round(composite, 1),
        "adp_sources": sorted(set(sources)),
        "adp_source_spread": round(max(adps) - min(adps), 1) if len(adps) > 1 else 0.0,
        "adp_format": dominant.actual_format,
        "adp_format_fallback": bool(dominant.format_fallback),
    }


def on_market_cushion(adp: float) -> float:
    """Half-width (in pick slots) of the on-market band at a given ``adp``.

    ``max(CUSHION_FLOOR, CUSHION_SLOPE * sqrt(adp))`` — tight at the top, widening
    with draft depth. Monotonic non-decreasing in ``adp``.
    """
    return max(CUSHION_FLOOR, CUSHION_SLOPE * math.sqrt(adp))


def market_axis(adp: float | None, overall: int) -> dict[str, Any]:
    """Reach/value delta + label for a pick at ``overall`` given its ``adp``.

    ``adp_delta = overall - adp`` (positive = value/bargain — drafted later than
    the market; negative = reach — drafted earlier). The *number* is always the
    literal pick gap; the *label* keys off the depth-scaled :func:`on_market_cushion`,
    so a pick can read "Value by 7" yet still be ``on_market`` if 7 sits inside its
    (deeper, wider) cushion. Returns nulls when there is no ADP — the market axis is
    unavailable, which is kept distinct from the pick's scoring availability.
    """
    if adp is None:
        return {"adp_delta": None, "market_label": None}
    delta = round(overall - adp, 1)
    cushion = on_market_cushion(adp)
    if delta > cushion:
        label = "value"
    elif delta < -cushion:
        label = "reach"
    else:
        label = "on_market"
    return {"adp_delta": delta, "market_label": label}


def season_adp_map(
    session: Session, season_id: int, cache: AnalyticsCache | None = None
) -> dict[int, dict[str, Any]]:
    """``player_id -> blended ADP`` for a season (cached per pipeline run).

    Reads the raw per-source rows from Phase 1 and blends them once; shared by the
    draft board, value, and tendencies surfaces.
    """
    if cache is None:
        return _build_season_adp_map(session, season_id)
    return cache.get_or_compute(
        session, f"season_adp_map:{season_id}", lambda: _build_season_adp_map(session, season_id)
    )


def _build_season_adp_map(session: Session, season_id: int) -> dict[int, dict[str, Any]]:
    by_player = player_adp_rows_for_season(session, season_id)
    out: dict[int, dict[str, Any]] = {}
    for player_id, rows in by_player.items():
        blend = blend_player_adp(rows)
        if blend is not None:
            out[player_id] = blend
    return out


# FFC is the only source carrying the full draft-week high/low/stdev spread
# (aggregated over late August); MFL/Sleeper are wider-window, softer aggregates.
# A season blended *without* FFC has genuinely less-precise reach/value reads.
_LIMITED_COVERAGE_NOTE = (
    "ADP coverage is limited this season — based on wider-window sources (no "
    "draft-week snapshot), so reach/value reads are less precise."
)


def adp_coverage(adp_map: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Season-level ADP coverage flag, derived from a built ``season_adp_map``.

    A season is **limited** when the union of sources blended across its players
    does not include ``ffc`` (the only draft-week-snapshot source). Data-driven —
    never a hardcoded year: if FFC restores a season the flag clears itself, and if
    a season loses FFC it trips, with no code change (read-only seam).
    """
    sources: set[str] = set()
    for blend in adp_map.values():
        sources.update(blend.get("adp_sources", ()))
    limited = bool(sources) and "ffc" not in sources
    return {
        "limited": limited,
        "sources": sorted(sources),
        "note": _LIMITED_COVERAGE_NOTE if limited else None,
    }


__all__ = [
    "ADP_DEFINITION",
    "ADP_SOURCE_WEIGHTS",
    "CUSHION_FLOOR",
    "CUSHION_SLOPE",
    "adp_coverage",
    "blend_player_adp",
    "market_axis",
    "on_market_cushion",
    "season_adp_map",
]
