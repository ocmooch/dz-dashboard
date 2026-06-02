"""Data-coverage summary for ``/v1/meta``.

Reads the database to report which seasons exist, which are scored, and whether
the historical reconstruction looks complete. The frontend uses this to drive
the "data as of" indicator and the honest-gap banners described in
``docs/03_DATA_ACCESS.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Matchup, Player, PlayerStatsScored, Season
from sqlalchemy import distinct, func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# A documented gap from the Phase 1 reliability map that we still can't detect
# per-run: availability snapshots only exist for the current season. It's a
# property of the data source, so it stays a constant and is revisited if Phase 1
# closes the gap. (DST scoring used to live here too, hardcoded False; it is now
# data-derived — see ``dst_scoring_complete`` — because the pipeline scores it.)
AVAILABILITY_CURRENT_SEASON_ONLY = True


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


def seasons_with_dst_scored(session: Session) -> list[int]:
    """Season years that have at least one *scored* team-defense (DEF) row.

    Joined through the player so it counts only DEF-position rows; the pipeline
    writes team-defense stats as DEF "players" and the engine scores them with
    the league's defense rules.
    """
    stmt = (
        select(distinct(Season.year))
        .join(PlayerStatsScored, PlayerStatsScored.season_id == Season.season_id)
        .join(Player, Player.player_id == PlayerStatsScored.player_id)
        .where(Player.position == "DEF")
        .order_by(Season.year)
    )
    rows = session.execute(stmt).scalars().all()
    return [int(y) for y in rows]


def dst_scoring_complete(session: Session) -> bool:
    """True when every scored season also has scored team-defense rows.

    This used to be a hardcoded ``False`` while DST scoring was deferred in the
    pipeline. Now that the pipeline ingests and scores team defense, we report it
    honestly and at season granularity: complete only when *every* scored season
    carries at least one scored DEF row, so a mid-backfill DB still reads False.
    A single team/week DEF row that is genuinely missing is a per-row gap the box
    score surfaces on its own (``team_defense_not_scored``); it does not flip this
    season-level capability flag.
    """
    scored = set(seasons_scored(session))
    if not scored:
        return False
    return scored <= set(seasons_with_dst_scored(session))


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
        "dst_scoring_complete": dst_scoring_complete(session),
    }
