"""Helpers shared across analytics modules.

Kept deliberately small: league resolution (the dashboard serves a single
league), name lookups, and the regular-season-week helper that every metric
needs so no view ever hardcodes 14 or 17 weeks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.api.errors import service_unavailable
from ff_pipeline.repository.models import League, Owner, Season, Team
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Seasons from this year onward use a consistent, documented tiebreaker; older
# seasons' NFL.com tiebreak history drifted (wins > head-to-head/conference >
# points-for), so computed orderings before this carry a caveat flag.
CONSISTENT_TIEBREAK_SINCE = 2019


def require_league(session: Session) -> League:
    """Return the league, or raise 503 if the pipeline has produced none yet."""
    league = session.execute(select(League).order_by(League.league_id)).scalars().first()
    if league is None:
        raise service_unavailable("No league data yet — run the Phase 1 pipeline first.")
    return league


def regular_season_weeks(session: Session, season: Season) -> int:
    """The season's regular-season week count, falling back to the max played
    week when the column is unset (never hardcode 14/17)."""
    if season.regular_season_weeks is not None:
        return int(season.regular_season_weeks)
    from ff_pipeline.repository.models import Matchup

    maxweek = session.execute(
        select(func.max(Matchup.week)).where(Matchup.season_id == season.season_id)
    ).scalar_one_or_none()
    return int(maxweek) if maxweek is not None else 0


def owner_name_map(session: Session) -> dict[int, str | None]:
    """owner_id -> display_name for every owner."""
    rows = session.execute(select(Owner.owner_id, Owner.display_name)).all()
    return {int(oid): name for oid, name in rows}


def owner_active_map(session: Session) -> dict[int, bool]:
    """owner_id -> is_active for every owner (managers still in the league)."""
    rows = session.execute(select(Owner.owner_id, Owner.is_active)).all()
    return {int(oid): bool(active) for oid, active in rows}


def team_owner_map(session: Session) -> dict[int, int]:
    """team_id -> owner_id for every team (career/rivalry metrics key on owner)."""
    rows = session.execute(select(Team.team_id, Team.owner_id)).all()
    return {int(tid): int(oid) for tid, oid in rows}
