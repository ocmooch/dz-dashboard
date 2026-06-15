"""Presentation-shape normalization for player injury reports.

Phase 1 ingests the full nflverse injury feed into ``player_injury_reports``
(``ff_pipeline.repository.queries.injury_reports_for_week``). This module turns
one report row into the small, display-ready field set the BFF surfaces on the
box score and the week-scoped team roster — so both views agree byte-for-byte.

The frontend renders these fields verbatim; all of the "what counts as a real
designation / a real body part / a short practice code" judgement lives here, in
Python, per the project's no-metric-math-in-web rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from ff_pipeline.repository.models import PlayerInjuryReport

# Game-status designations we treat as a real badge-worthy report. nflverse also
# emits blanks (practice-only rows) and the odd free-text "Note"; those are not a
# game status, so they collapse to ``None`` and no badge shows. "Probable" was a
# real NFL designation retired after 2015 — kept so pre-2016 box scores stay honest.
_GAME_STATUSES = frozenset({"Out", "Doubtful", "Questionable", "Probable"})

# nflverse spells practice participation out in full; the badge wants a short code.
_PRACTICE_CODES = {
    "Did Not Participate In Practice": "DNP",
    "Limited Participation in Practice": "Ltd",
    "Full Participation in Practice": "Full",
    "Out (Definitely Will Not Play)": "Out",
}


class InjuryFields(TypedDict):
    injury_status: str | None
    injury_body_part: str | None
    injury_secondary: str | None
    injury_practice_status: str | None


def _clean(value: str | None) -> str | None:
    """Trim and treat empty strings as missing."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _body_part(value: str | None) -> str | None:
    """A body part, dropping nflverse non-injury notes.

    The injury columns occasionally carry free text like "Not injury related -
    personal matter" / "...- resting player" (load management, not an injury);
    surfacing that as a body part would be misleading, so anything flagged as
    not-injury-related is suppressed. Applies to both primary and secondary.
    """
    cleaned = _clean(value)
    if cleaned is None:
        return None
    if cleaned.lower().startswith("not injury related"):
        return None
    return cleaned


def injury_fields(report: PlayerInjuryReport | None) -> InjuryFields:
    """Normalize one report (or its absence) into the box/roster field set.

    ``injury_status`` is ``None`` for any row without a real game designation,
    which is what gates the frontend badge — so practice-only rows never badge.
    """
    if report is None:
        return InjuryFields(
            injury_status=None,
            injury_body_part=None,
            injury_secondary=None,
            injury_practice_status=None,
        )
    status = _clean(report.report_status)
    if status not in _GAME_STATUSES:
        status = None
    practice = _clean(report.practice_status)
    return InjuryFields(
        injury_status=status,
        injury_body_part=_body_part(report.report_primary_injury),
        injury_secondary=_body_part(report.report_secondary_injury),
        injury_practice_status=_PRACTICE_CODES.get(practice) if practice else None,
    )
