"""Player stat aggregations owned by the dashboard (``analytics/stats.py``).

Season totals live here rather than in the Phase-1 ``queries.season_totals``
because the math is the dashboard's: Phase 1 sums **every** scored week, which
includes NFL post-season weeks beyond the fantasy schedule and inflates a
player's season line. We cap the sum at the season's fantasy championship week
using the per-season :mod:`season_schedule` model. The output shape mirrors the
Phase-1 query (so the API contract is unchanged); only the values are corrected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Player, PlayerStatsScored
from ff_pipeline.repository.queries import player_season_teams
from sqlalchemy import func, select

from ff_dashboard.analytics.season_schedule import season_schedule

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
    from sqlalchemy.orm import Session


def season_totals(
    session: Session, season: Season, *, position: str | None = None
) -> list[dict[str, Any]]:
    """Per-player fantasy-season totals for ``season``, capped to fantasy weeks.

    Sums ``total_points`` over weeks ``<= championship_week`` (from the season
    schedule), so post-fantasy NFL weeks never inflate the total. Returns rows of
    ``{player_id, name_full, position, nfl_team, total_points, weeks_played}``
    ordered by total descending. A season with no ``player_stats_scored`` rows
    returns ``[]`` — a gap, not zero-filled.
    """
    schedule = season_schedule(session, season)
    stmt = (
        select(
            Player.player_id,
            Player.name_full,
            Player.position,
            Player.nfl_team,
            func.sum(PlayerStatsScored.total_points).label("total"),
            func.count(PlayerStatsScored.scored_id).label("weeks"),
        )
        .join(PlayerStatsScored, PlayerStatsScored.player_id == Player.player_id)
        .where(
            PlayerStatsScored.season_id == season.season_id,
            PlayerStatsScored.week <= schedule.championship_week,
        )
        .group_by(Player.player_id, Player.name_full, Player.position, Player.nfl_team)
        .order_by(func.sum(PlayerStatsScored.total_points).desc())
    )
    if position is not None:
        stmt = stmt.where(Player.position == position)
    rows = session.execute(stmt).all()
    # Season-correct NFL team (a 2015 Raider reads "OAK", not "LV"), batched to
    # resolve the whole leaderboard page in one query. Falls back to the current
    # snapshot on players.nfl_team when no per-week team is stored that season.
    season_teams = player_season_teams(session, [r.player_id for r in rows], season.year)
    return [
        {
            "player_id": r.player_id,
            "name_full": r.name_full,
            "position": r.position,
            "nfl_team": season_teams.get(r.player_id) or r.nfl_team,
            "total_points": float(r.total or 0.0),
            "weeks_played": int(r.weeks or 0),
        }
        for r in rows
    ]
