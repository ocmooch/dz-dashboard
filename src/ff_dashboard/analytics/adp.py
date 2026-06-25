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

# Picks within this many slots of the consensus read as drafted "on market"
# rather than a reach or a value — keeps tiny deltas from being over-read.
ON_MARKET_BAND = 1.0

_WEIGHTS_PHRASE = ", ".join(f"{s.upper()} {w:g}" for s, w in ADP_SOURCE_WEIGHTS.items())

ADP_DEFINITION = (
    "ADP is the consensus average draft position blended across public sources "
    "(Fantasy Football Calculator, MyFantasyLeague, Sleeper), weighted "
    f"{_WEIGHTS_PHRASE} and matched to this league's format (full-PPR; half-PPR "
    "in 2010), 12-team. It is the closest public market to this league — not its "
    "own valuations. Reach / value is the gap between where the league drafted a "
    "player and the consensus: drafted earlier than ADP is a reach, later is a value."
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


def market_axis(adp: float | None, overall: int) -> dict[str, Any]:
    """Reach/value delta + label for a pick at ``overall`` given its ``adp``.

    ``adp_delta = overall - adp`` (positive = value/bargain — drafted later than
    the market; negative = reach — drafted earlier). Returns nulls when there is
    no ADP — the market axis is unavailable, which is kept distinct from the
    pick's scoring availability.
    """
    if adp is None:
        return {"adp_delta": None, "market_label": None}
    delta = round(overall - adp, 1)
    if delta > ON_MARKET_BAND:
        label = "value"
    elif delta < -ON_MARKET_BAND:
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


__all__ = [
    "ADP_DEFINITION",
    "ADP_SOURCE_WEIGHTS",
    "ON_MARKET_BAND",
    "blend_player_adp",
    "market_axis",
    "season_adp_map",
]
