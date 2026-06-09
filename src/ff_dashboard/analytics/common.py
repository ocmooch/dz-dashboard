"""Helpers shared across analytics modules.

Kept deliberately small: league resolution (the dashboard serves a single
league), name lookups, and the regular-season-week helper that every metric
needs so no view ever hardcodes 14 or 17 weeks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.api.errors import service_unavailable
from ff_pipeline.repository.models import League, Matchup, Owner, Season, Team
from sqlalchemy import distinct, func, select

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
    maxweek = session.execute(
        select(func.max(Matchup.week)).where(Matchup.season_id == season.season_id)
    ).scalar_one_or_none()
    return int(maxweek) if maxweek is not None else 0


def played_season_ids(session: Session) -> set[int]:
    """season_ids that have at least one played game (a ``Matchup`` row).

    A season created for an upcoming year — teams and offseason rosters seeded
    but no games played yet — has no matchups. Every season-enumerating surface
    (the season selector, the museum timeline, manager trajectories, the
    coverage view) filters on this set so the dashboard never shows an empty,
    resultless season; it reappears automatically once its first games land.
    Data-driven on played games — it never keys on a hardcoded year."""
    rows = session.execute(select(distinct(Matchup.season_id))).scalars().all()
    return {int(s) for s in rows}


def displayed_seasons(session: Session, league_id: str) -> list[Season]:
    """``list_seasons_for_league`` minus not-yet-played seasons.

    The single canonical season list for display surfaces — see
    ``played_season_ids`` for why upcoming-but-unplayed seasons are withheld."""
    from ff_pipeline.repository.queries import list_seasons_for_league

    played = played_season_ids(session)
    return [s for s in list_seasons_for_league(session, league_id) if int(s.season_id) in played]


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
