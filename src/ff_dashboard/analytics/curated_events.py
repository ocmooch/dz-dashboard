"""Curated narrative league events for the history timeline.

Most timeline rows are derived from ``setting_change`` transactions + state
diffs. A narrative NFL event (e.g. the 2022 Damar Hamlin no-contest) has no
transaction behind it, so it lives here as a small, hand-authored event source
that returns ``LeagueChangeDetail``-shaped dicts keyed by season year and is
merged into ``league_timeline()`` alongside ``setting_change_events()``.

Each curated event is **gated on verifiable DB state** so the dashboard stays
honest: the Hamlin event only appears once the upstream resolution has landed
(i.e. the ``hamlin_substitute`` provenance exists on the 2022 wk17 rosters).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import TeamRoster
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Grounded in public record: the NFL ruled the suspended 2022 Week-17
# Bills@Bengals game a no-contest (NFL.com / ESPN); the substitute scores are
# verifiable public stats (the Week-17 box score plus the Week-19 stat lines).
_HAMLIN_SUMMARY = (
    "The NFL Week-17 Bills@Bengals game (Jan 2 2023) was suspended after Damar "
    "Hamlin's cardiac arrest and ruled a no-contest by the NFL — never replayed "
    "(NFL.com / ESPN). The league resolved its affected playoff matchups by "
    "counting, for each affected player, their Week-17 stats from before play "
    "stopped plus their Week-19 (Wild Card) game; Week 18 was skipped. The "
    "substitute scores are reconstructed from public data (the Week-17 box score "
    "plus the Week-19 stat lines); a recovered private league note corroborated "
    "only the Week-19 component and was incomplete. The correction flips the 2022 "
    "championship to Smokin Doubs over CMC Rules Everything Around Me."
)

_HAMLIN_EVENT_YEAR = 2022


def _hamlin_event() -> dict[str, Any]:
    """The 2022 Hamlin no-contest event, in ``LeagueChangeDetail`` shape."""
    return {
        "category": "league_event",
        "title": "2022 championship resolved after the Hamlin no-contest",
        "summary": _HAMLIN_SUMMARY,
        "before": "CMC Rules Everything Around Me (as originally recorded)",
        "after": "Smokin Doubs (Week-17 partial + Week-19 substitution)",
        "source": "league_ruling",
        "certainty": "verified",
        "changed_at": "2023-01-02",
        "participants_joined": None,
        "participants_left": None,
        "description_gap": False,
        "tier": "T1",
        "human_label": "Hamlin no-contest championship resolution",
        "phase": "in_season",
        "event_group_key": None,
        "missing_context": False,
        "members": [],
        "canonical_type": "league_event",
    }


def _hamlin_resolution_present(session: Session) -> bool:
    """True once the upstream 2022 wk17 no-contest fix has landed in the DB."""
    stmt = (
        select(func.count())
        .select_from(TeamRoster)
        .where(
            TeamRoster.season_year == _HAMLIN_EVENT_YEAR,
            TeamRoster.week == 17,
            func.json_extract(TeamRoster.extra_data, "$.hamlin_substitute").is_not(None),
        )
    )
    return bool(session.execute(stmt).scalar_one())


def curated_events_by_year(session: Session) -> dict[int, list[dict[str, Any]]]:
    """Curated narrative events keyed by season year (empty when none apply)."""
    events: dict[int, list[dict[str, Any]]] = {}
    if _hamlin_resolution_present(session):
        events.setdefault(_HAMLIN_EVENT_YEAR, []).append(_hamlin_event())
    return events


__all__ = ["curated_events_by_year"]
