"""Insight primitives — the non-viz "discovery engine" seed (``analytics/insights.py``).

Where the **Viz Lab** holds visual exhibits, this is the parallel **Insights Lab**: a
library of *insight primitives*. Each primitive is a named, tested function that
**computes a structured finding** from metrics the dashboard already has, and a separate
**narrator** renders prose from that finding's facts.

The trust seam is the project's own move, reused. Just as the SPA is trustworthy because
it does no math, the narrator (a deterministic template today, an LLM later) only
*arranges* numbers it is handed — it **never computes one**. Every fact carries provenance
to a tested metric and its serving endpoint, so a claim can always be traced back to a
view. This is the Phase-3 "insight-primitive library" v0, built so an LLM narration /
selection layer can drop in later with the ``facts`` unchanged.

Honesty rule holds: a primitive returns ``None`` when a data gap means the finding can't
be made — an **absent** insight, never a fabricated one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.queries import get_season

from ff_dashboard.analytics.draft import draft_value
from ff_dashboard.analytics.standings import standings_insights

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ff_dashboard.cache import AnalyticsCache

# A "full" fantasy regular season is 13+ weeks here (the league ran 1-13, later 1-14).
# A schedule-luck read on a complete season is high-confidence; a partial one is softer.
_FULL_REGULAR_SEASON_WEEKS = 13


def _fact(label: str, value: Any, unit: str | None = None) -> dict[str, Any]:
    """One traceable number the narrator may arrange but must not recompute."""
    return {"label": label, "value": value, "unit": unit}


def _wins(n: float) -> str:
    """'1 win' / '2.5 wins' — narration helper, formatting only."""
    text = f"{n:g}"
    return f"{text} win" if n == 1 else f"{text} wins"


def schedule_luck_insight(
    session: Session, season_id: int, _cache: AnalyticsCache | None = None
) -> dict[str, Any] | None:
    """The season's unluckiest manager, from the all-play / Expected-Wins keystone.

    Reuses :func:`analytics.standings.standings_insights` (``most_robbed``) — the most
    beloved "hidden truth" in fantasy. Computes nothing new; selects the finding and
    hands its numbers to the narrator. ``None`` when the season has no completed
    matchups (no all-play résumé to judge luck against).
    """
    ins = standings_insights(session, season_id)
    if ins is None or not ins.get("available"):
        return None
    robbed = ins.get("most_robbed")
    if robbed is None:
        return None

    year = ins["season_year"]
    actual = robbed["actual_wins"]
    expected = robbed["expected_wins"]
    gap = round(expected - actual, 2)
    through_week = ins.get("through_week") or 0
    owner = robbed.get("owner_name") or robbed.get("team_name") or "Unknown"

    facts = [
        _fact("Actual wins", actual),
        _fact("Expected (all-play) wins", expected),
        _fact("Luck gap", gap, "wins"),
        _fact("All-play win %", round(robbed["all_play_win_pct"] * 100, 1), "%"),
    ]
    narration = (
        f"In {year}, {owner} was the league's unluckiest manager — "
        f"{_wins(actual)} despite an all-play résumé worth {_wins(expected)}, "
        f"a {_wins(gap)} gap, the largest in the league. The schedule, not the roster, "
        f"set the record."
    )
    return {
        "kind": "schedule_luck",
        "title": f"Schedule luck — {year}",
        "narration": narration,
        "facts": facts,
        "subject": {"owner_id": robbed.get("owner_id"), "owner_name": owner},
        "provenance": {
            "metric": "standings.schedule_luck",
            "endpoint": f"/v1/seasons/{season_id}/standings/insights",
        },
        "confidence": "high" if through_week >= _FULL_REGULAR_SEASON_WEEKS else "medium",
    }


def draft_market_insight(
    session: Session, season_id: int, cache: AnalyticsCache | None = None
) -> dict[str, Any] | None:
    """The draft's biggest reach, from the recalibrated market (ADP) axis.

    Reuses :func:`analytics.draft.draft_value` (``reaches[0]`` — already ranked by the
    depth-scaled cushion, PR #119). Confidence follows the season's ADP coverage: a
    season blended without FFC's draft-week snapshot is a softer read, and its coverage
    note rides along for the builder to surface. ``None`` when no draft was captured.
    """
    value = draft_value(session, season_id, cache)
    if value is None or not value.get("available"):
        return None
    reaches = value.get("reaches") or []
    if not reaches:
        return None

    top = reaches[0]
    coverage = value.get("adp_coverage") or {}
    limited = bool(coverage.get("limited"))
    player = top.get("player_name") or "A pick"
    overall = top["overall"]
    adp = top.get("adp")
    delta = abs(top.get("adp_delta") or 0)

    facts = [
        _fact("Drafted at", overall, "overall"),
        _fact("Consensus ADP", adp),
        _fact("Picks ahead of market", round(delta, 1)),
    ]
    narration = (
        f"The draft's biggest reach: {player} went #{overall} overall, "
        f"{round(delta, 1):g} picks ahead of a consensus ADP of {adp}. "
    ) + (
        "ADP coverage is limited this season, so read it as a soft signal."
        if limited
        else "Drafted well before the market would have."
    )
    return {
        "kind": "draft_market",
        "title": f"Biggest reach — {value['season_year']} draft",
        "narration": narration,
        "facts": facts,
        "subject": {"owner_id": top.get("owner_id"), "owner_name": top.get("owner_name")},
        "provenance": {
            "metric": "draft.market_axis",
            "endpoint": f"/v1/seasons/{season_id}/draft/value",
        },
        "confidence": "medium" if limited else "high",
        # Carried for the builder to lift into season-level notes (not displayed per-card).
        "_coverage_note": coverage.get("note") if limited else None,
    }


# The ordered primitive registry. Adding the next insight is appending one function —
# the lab's whole point. Each takes ``(session, season_id, cache)`` and returns an
# Insight dict or None.
_PRIMITIVES = (schedule_luck_insight, draft_market_insight)


def season_insights(
    session: Session, season_id: int, cache: AnalyticsCache | None = None
) -> dict[str, Any]:
    """Run every insight primitive for a season; drop the ones that found nothing.

    ``available`` is false only when *no* primitive fired (a genuinely thin season),
    distinct from any single primitive's gap. Season-level honesty notes (e.g. limited
    ADP coverage) are collected here, deduped, so a card never has to editorialize.
    """
    season = get_season(session, season_id)
    insights: list[dict[str, Any]] = []
    notes: list[str] = []
    for primitive in _PRIMITIVES:
        result = primitive(session, season_id, cache)
        if result is None:
            continue
        note = result.pop("_coverage_note", None)
        if note and note not in notes:
            notes.append(note)
        insights.append(result)

    return {
        "season_id": season_id,
        "season_year": season.year if season is not None else None,
        "available": bool(insights),
        "insights": insights,
        "notes": notes,
    }


__all__ = [
    "draft_market_insight",
    "schedule_luck_insight",
    "season_insights",
]
