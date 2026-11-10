"""The in-progress season at a glance (Sleeper D3): ``GET /v1/seasons/current``.

Composes existing analytics only (no new math): the last finalized week's results and the
unfinished week's pairings from :func:`matchups.week_matchups`, and the top of the standings from
:func:`standings.compute_standings` (finalized weeks only). The unfinished week is unscored, so its
pairings carry no scores (user rule, ``docs/sleeper/00`` §3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_dashboard.analytics.common import played_season_ids
from ff_dashboard.analytics.matchups import week_matchups
from ff_dashboard.analytics.platform import current_season as current_season_ids
from ff_dashboard.analytics.platform import season_provenance, week_state
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

#: rows of the standings shown on the Home "This week" block
STANDINGS_TOP = 4


def _games(session: Session, season_id: int, week: int | None) -> list[dict[str, Any]]:
    if week is None:
        return []
    data = week_matchups(session, season_id, week)
    return list(data["games"]) if data is not None else []


def current_season(session: Session) -> dict[str, Any]:
    """The in-progress season, or ``available: false`` (``no_current_season``) off-season."""
    season_id = current_season_ids(session)["current_season_id"]
    if season_id is not None and season_id not in played_season_ids(session):
        season_id = None  # an in-progress season with no games yet (e.g. before go-live)
    standings = compute_standings(session, season_id) if season_id is not None else None
    if season_id is None or standings is None:
        return {"available": False, "reason": "no_current_season"}

    weeks = week_state(session, season_id)
    last = weeks["last_finalized_week"]
    pending = weeks["pending_week"]
    return {
        "available": True,
        "reason": None,
        "season_id": season_id,
        "season_year": standings["season_year"],
        **season_provenance(session, season_id),
        "regular_season_weeks": standings["regular_season_weeks"],
        "last_finalized_week": last,
        "pending_week": pending,
        "latest_results": _games(session, season_id, last),
        "pending_pairings": _games(session, season_id, pending),
        "standings_top": standings["rows"][:STANDINGS_TOP],
    }
