"""Player stat aggregations owned by the dashboard (``analytics/stats.py``).

Two leaderboards live here rather than in the Phase-1 ``queries`` because the
math is the dashboard's:

* **Season totals** — Phase 1 sums *every* scored week, which includes NFL
  post-season weeks beyond the fantasy schedule and inflates a player's line. We
  cap the sum at the season's fantasy championship week (per-season
  :mod:`season_schedule`).
* **Top scorers** — the per-week leaderboard.

Both also correct the *score itself*: ``player_stats_scored.total_points`` omits
the NFL.com bonuses the league awarded, so each week is read through
:func:`ff_dashboard.analytics.scoring.authoritative_week_points`
(``coalesce(nfl_com_points, total_points)`` — the same score the box score and
records book show), and both leaderboards are scoped to **rostered-ever** players
(:func:`~ff_dashboard.analytics.scoring.rostered_ever`): the reconstruction
scores the whole NFL, but a player nobody ever rostered is not league-relevant.
A rostered-ever player still contributes *every* scored week, including weeks
they were not on a roster (player credit, not a team/owner record). The output
shapes mirror the Phase-1 queries, so the API contract is unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Player, PlayerStatsScored, Season, TeamRoster
from ff_pipeline.repository.queries import _player_week_teams, player_season_teams
from sqlalchemy import func, select

from ff_dashboard.analytics.scoring import authoritative_week_points, rostered_ever
from ff_dashboard.analytics.season_schedule import season_schedule

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _roster_join_on(season_year: int) -> Any:
    """LEFT-JOIN predicate tying a roster row to a scored player-week.

    There is at most one ``team_rosters`` row per ``(player_id, season_year,
    week)``, so this never multiplies a scored row — the coalesce stays exact for
    both the per-week leaderboard and the season SUM.
    """
    return (
        (TeamRoster.player_id == PlayerStatsScored.player_id)
        & (TeamRoster.week == PlayerStatsScored.week)
        & (TeamRoster.season_year == season_year)
    )


def top_scorers(
    session: Session,
    *,
    season_year: int,
    week: int | None,
    position: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Top single-week player scores for a season, bonus-inclusive and league-scoped.

    Each row is one ``(player, week)`` score read as
    ``coalesce(nfl_com_points, total_points)`` so NFL.com bonuses the
    reconstruction omits are reflected (e.g. Vick 2010 wk10 = 63.32, not 58.32),
    and the coalesce is applied **before** the order/limit so a bonus can change
    the ranking. Restricted to rostered-ever players (a never-rostered nflverse
    player is not a league leaderboard entry). Returns rows of
    ``{player_id, name_full, position, nfl_team, season_year, week, points}``.
    Dict keys mirror the former Phase-1 ``queries.top_scorers`` so the API
    contract is unchanged.
    """
    points = authoritative_week_points()
    stmt = (
        select(
            Player.player_id,
            Player.name_full,
            Player.position,
            Player.nfl_team,
            PlayerStatsScored.week,
            points.label("points"),
        )
        .join(PlayerStatsScored, PlayerStatsScored.player_id == Player.player_id)
        .join(Season, Season.season_id == PlayerStatsScored.season_id)
        .outerjoin(TeamRoster, _roster_join_on(season_year))
        .where(Season.year == season_year, rostered_ever())
    )
    if week is not None:
        stmt = stmt.where(PlayerStatsScored.week == week)
    if position is not None:
        stmt = stmt.where(Player.position == position)
    stmt = stmt.where(points.is_not(None)).order_by(points.desc()).limit(limit)
    rows = session.execute(stmt).all()
    # Each row is a single (player, week) score, so render the team the player
    # was on that exact week; fall back to the current snapshot when no per-week
    # team is stored (same season-correct read the Phase-1 query used).
    week_teams = _player_week_teams(session, [(r.player_id, r.week) for r in rows], season_year)
    return [
        {
            "player_id": r.player_id,
            "name_full": r.name_full,
            "position": r.position,
            "nfl_team": week_teams.get((r.player_id, r.week)) or r.nfl_team,
            "season_year": season_year,
            "week": r.week,
            "points": float(r.points or 0.0),
        }
        for r in rows
    ]


def season_totals(
    session: Session, season: Season, *, position: str | None = None
) -> list[dict[str, Any]]:
    """Per-player fantasy-season totals for ``season``, capped to fantasy weeks.

    Sums each week as ``coalesce(nfl_com_points, total_points)`` (so NFL.com
    bonuses count) over weeks ``<= championship_week`` (from the season schedule),
    so post-fantasy NFL weeks never inflate the total. Scoped to rostered-ever
    players; a rostered-ever player still contributes every scored week, even ones
    they were not on a roster (we do **not** strict-roster-scope the weeks — top
    season scorers have partial roster coverage and dropping unrostered weeks
    would deflate the total). Returns rows of ``{player_id, name_full, position,
    nfl_team, total_points, weeks_played}`` ordered by total descending. A season
    with no scored rows returns ``[]`` — a gap, not zero-filled.
    """
    schedule = season_schedule(session, season)
    points = authoritative_week_points()
    stmt = (
        select(
            Player.player_id,
            Player.name_full,
            Player.position,
            Player.nfl_team,
            func.sum(points).label("total"),
            func.count(PlayerStatsScored.scored_id).label("weeks"),
        )
        .join(PlayerStatsScored, PlayerStatsScored.player_id == Player.player_id)
        .outerjoin(TeamRoster, _roster_join_on(season.year))
        .where(
            PlayerStatsScored.season_id == season.season_id,
            PlayerStatsScored.week <= schedule.championship_week,
            rostered_ever(),
        )
        .group_by(Player.player_id, Player.name_full, Player.position, Player.nfl_team)
        .order_by(func.sum(points).desc())
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
