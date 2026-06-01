"""Data-coverage summary for ``/v1/meta``.

Reads the database to report which seasons exist, which are scored, and whether
the historical reconstruction looks complete. The frontend uses this to drive
the "data as of" indicator and the honest-gap banners described in
``docs/03_DATA_ACCESS.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Matchup, PlayerStatsScored, Season
from sqlalchemy import distinct, func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Known, documented gaps from the Phase 1 reliability map. These are properties
# of the data sources, not something we can fully detect per-run, so they are
# surfaced as constants and revisited if Phase 1 closes the gap.
AVAILABILITY_CURRENT_SEASON_ONLY = True
DST_SCORING_COMPLETE = False


def seasons_present(session: Session) -> list[int]:
    """All season years known to the database, ascending."""
    rows = session.execute(select(Season.year).order_by(Season.year)).scalars().all()
    return [int(y) for y in rows]


def seasons_scored(session: Session) -> list[int]:
    """Season years that have at least one scored stat row, ascending."""
    stmt = (
        select(distinct(Season.year))
        .join(PlayerStatsScored, PlayerStatsScored.season_id == Season.season_id)
        .order_by(Season.year)
    )
    rows = session.execute(stmt).scalars().all()
    return [int(y) for y in rows]


def reconstruction_complete(session: Session) -> bool:
    """True when every completed season has a champion and matchup history.

    The reconstruction (Phase 1 item C5) fills champions, records, lineups, and
    matchups. We treat it as complete when no ``completed`` season is missing a
    ``champion_team_id`` or has zero matchup rows.
    """
    completed = list(
        session.execute(
            select(Season.season_id, Season.champion_team_id).where(Season.status == "completed")
        ).all()
    )
    if not completed:
        return False
    weeks_by_season: dict[int, int] = {
        int(season_id): int(count)
        for season_id, count in session.execute(
            select(Matchup.season_id, func.count(Matchup.matchup_id)).group_by(Matchup.season_id)
        ).all()
    }
    for season_id, champion_team_id in completed:
        if champion_team_id is None:
            return False
        if weeks_by_season.get(season_id, 0) == 0:
            return False
    return True


def compute_coverage(session: Session) -> dict[str, object]:
    """Assemble the full coverage payload for ``/v1/meta``."""
    scored = seasons_scored(session)
    return {
        "seasons_present": seasons_present(session),
        "seasons_scored": scored,
        "scored_year_min": scored[0] if scored else None,
        "scored_year_max": scored[-1] if scored else None,
        "reconstruction_complete": reconstruction_complete(session),
        "availability_current_season_only": AVAILABILITY_CURRENT_SEASON_ONLY,
        "dst_scoring_complete": DST_SCORING_COMPLETE,
    }
