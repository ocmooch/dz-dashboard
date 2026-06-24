"""Helpers shared across analytics modules.

Kept deliberately small: league resolution (the dashboard serves a single
league), name lookups, and the regular-season-week helper that every metric
needs so no view ever hardcodes 14 or 17 weeks.
"""

from __future__ import annotations

from collections import defaultdict
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

# A departed manager with at least this many *played* seasons is still a
# long-tenure presence in the league's history (Tier C) and stays eligible for
# the all-time "best of" rankings; below it a short-stint departed owner is
# deprioritized so they never outrank an active or legacy manager. Active
# managers always qualify regardless of tenure (Tier A). This mirrors the
# active/min-sample gates the rivalry surfaces already use — it never *hides* an
# owner, only orders them. The bar sits well clear of the real cohort gap
# (long-stint departed owners have 10+ seasons; the rest have ≤3).
SIGNIFICANT_STINT_SEASONS = 5


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


def owner_seasons_played_map(session: Session) -> dict[int, int]:
    """owner_id -> count of distinct *played* seasons (matches career tenure).

    Counts only seasons with games on record (see :func:`played_season_ids`), so
    an owner seeded into an upcoming-but-unplayed season is not credited tenure
    they have not yet earned. This is the same season set the career table sums."""
    played = played_season_ids(session)
    by_owner: dict[int, set[int]] = defaultdict(set)
    for oid, sid in session.execute(select(Team.owner_id, Team.season_id)).all():
        if int(sid) in played:
            by_owner[int(oid)].add(int(sid))
    return {oid: len(seasons) for oid, seasons in by_owner.items()}


def owner_qualified_map(session: Session) -> dict[int, bool]:
    """owner_id -> eligible for all-time "best of" rankings.

    True when the manager is still active **or** has a significant stint
    (``seasons_played >= SIGNIFICANT_STINT_SEASONS``). Surfaces that crown a
    league-best read this so a short-stint departed owner is never ranked above
    an active or legacy manager; the owner is still shown, just not crowned.
    See :data:`SIGNIFICANT_STINT_SEASONS`."""
    active = owner_active_map(session)
    seasons = owner_seasons_played_map(session)
    return {
        oid: bool(active.get(oid, True)) or seasons.get(oid, 0) >= SIGNIFICANT_STINT_SEASONS
        for oid in owner_name_map(session)
    }
