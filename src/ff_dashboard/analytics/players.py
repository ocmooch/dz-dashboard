"""Player views: scoring history, ownership, top scorers, season totals,
availability. Mostly light aggregation over Phase 1 facts, with honest gap
handling for unscored seasons and historical availability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Owner, Player, PlayerStatsScored, Season, Team, TeamRoster
from ff_pipeline.repository.queries import (
    availability_timeline,
    get_player,
    player_availability_for_season,
    player_ownership,
)
from sqlalchemy import func, select

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.coverage import seasons_scored

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def list_player_index(
    session: Session,
    *,
    name: str | None = None,
    position: str | None = None,
    nfl_team: str | None = None,
    scope: str = "league",
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Paginated player index, scoped to league relevance by default.

    A player is *league-relevant* when ``last_rostered_season`` is non-null —
    i.e. someone in the league owned them at some point. That column is the
    pipeline's materialized rostered-span (derived from ``team_rosters``); we
    read it directly rather than re-deriving the span with a GROUP BY join. The
    Phase 1 DB also carries the broader nflverse universe (players the pipeline
    scored but nobody ever rostered, plus stub/metadata rows); those are noise
    for a league players view, so ``scope="league"`` (the default) excludes
    them. ``scope="all"`` opts back into the full universe.

    Each row carries the player's rostered-season span (straight from the
    columns), so the caller can render relevance at a glance without the SPA
    doing any joins. Relevance is filtered *before* paging, so page sizes stay
    correct.
    """
    stmt = select(Player)
    if name is not None:
        stmt = stmt.where(Player.name_full.ilike(f"%{name}%"))
    if position is not None:
        stmt = stmt.where(Player.position == position)
    if nfl_team is not None:
        stmt = stmt.where(Player.nfl_team == nfl_team)
    if scope != "all":
        stmt = stmt.where(Player.last_rostered_season.isnot(None))
    stmt = stmt.order_by(Player.name_full).offset(offset).limit(limit)
    players = list(session.execute(stmt).scalars().all())

    return [
        {
            "player_id": p.player_id,
            "name_full": p.name_full,
            "position": p.position,
            "nfl_team": p.nfl_team,
            "first_rostered_season": p.first_rostered_season,
            "last_rostered_season": p.last_rostered_season,
        }
        for p in players
    ]


def player_scoring(session: Session, player_id: int, season_year: int) -> dict[str, Any] | None:
    """Weekly league points (+ breakdown) for a (player, season).

    Returns ``available: false`` for seasons with no scored rows rather than an
    empty/zero series.
    """
    if get_player(session, player_id) is None:
        return None

    if season_year not in set(seasons_scored(session)):
        return {
            "player_id": player_id,
            "season_year": season_year,
            "available": False,
            "reason": "season_unscored",
            "weeks": [],
        }

    rows = session.execute(
        select(
            PlayerStatsScored.week,
            PlayerStatsScored.total_points,
            PlayerStatsScored.points_breakdown,
        )
        .join(Season, Season.season_id == PlayerStatsScored.season_id)
        .where(PlayerStatsScored.player_id == player_id, Season.year == season_year)
        .order_by(PlayerStatsScored.week)
    ).all()
    weeks: list[dict[str, Any]] = [
        {
            "week": int(w),
            "points": round(float(pts), 2) if pts is not None else None,
            "breakdown": breakdown or {},
        }
        for w, pts, breakdown in rows
    ]
    total = round(sum(float(pts) for _, pts, _ in rows if pts is not None), 2)
    return {
        "player_id": player_id,
        "season_year": season_year,
        "available": True,
        "total_points": total,
        "weeks": weeks,
    }


def ownership_timeline(session: Session, player_id: int) -> dict[str, Any] | None:
    """Which league teams owned the player and when (None if no such player).

    Phase 1 stores one roster row per (season, week), so a season-long hold is
    ~17 near-identical rows — rendered raw, that *looks* like the player bounced
    between owners. Collapse consecutive weeks on the same team within a season
    into a single tenure span (``week_start``..``week_end``); a mid-season trade
    or a new season starts a fresh span, so a genuine owner change stays legible
    instead of buried. Rows arrive ordered by (season_year, week).
    """
    if get_player(session, player_id) is None:
        return None
    spans: list[dict[str, Any]] = []
    for roster, team in player_ownership(session, player_id):
        last = spans[-1] if spans else None
        if last is not None and (
            last["team_id"] == roster.team_id and last["season_year"] == roster.season_year
        ):
            last["week_end"] = roster.week
            last["weeks"] += 1
        else:
            spans.append(
                {
                    "team_id": roster.team_id,
                    "team_name": team.team_name,
                    "season_year": roster.season_year,
                    "week_start": roster.week,
                    "week_end": roster.week,
                    "weeks": 1,
                    "acquisition_type": roster.acquisition_type,
                }
            )
    seasons = [s["season_year"] for s in spans]
    return {
        "player_id": player_id,
        "first_rostered_season": min(seasons) if seasons else None,
        "last_rostered_season": max(seasons) if seasons else None,
        "events": spans,
    }


def availability(session: Session, player_id: int, season_year: int) -> dict[str, Any] | None:
    """Per-week availability for a player+season.

    Availability is current-season-only in Phase 1; any other season returns
    ``available: false`` with the documented reason, never a fabricated status.
    """
    if get_player(session, player_id) is None:
        return None

    current = require_league(session).current_season_year
    if current is None or season_year != current:
        return {
            "player_id": player_id,
            "season_year": season_year,
            "available": False,
            "reason": "availability_history_not_reconstructable",
            "weeks": [],
        }

    rows = player_availability_for_season(session, player_id, season_year)
    if not rows:
        return {
            "player_id": player_id,
            "season_year": season_year,
            "available": False,
            "reason": "no_availability_rows",
            "weeks": [],
        }
    return {
        "player_id": player_id,
        "season_year": season_year,
        "available": True,
        "weeks": [
            {
                "week": r.week,
                "status": r.status,
                "owning_team_id": r.owning_team_id,
                "is_pre_kickoff_snapshot": r.is_pre_kickoff_snapshot,
            }
            for r in rows
        ],
    }


def has_any_availability(session: Session, player_id: int) -> bool:
    """Whether the player has any availability rows at all (any season)."""
    return bool(availability_timeline(session, player_id))


def player_insights(session: Session, player_id: int) -> dict[str, Any] | None:
    """Best scoring and league ownership summary for a player."""
    if get_player(session, player_id) is None:
        return None

    ownership = ownership_timeline(session, player_id)
    best_week_row = session.execute(
        select(Season.year, PlayerStatsScored.week, PlayerStatsScored.total_points)
        .join(Season, Season.season_id == PlayerStatsScored.season_id)
        .where(PlayerStatsScored.player_id == player_id)
        .order_by(PlayerStatsScored.total_points.desc())
        .limit(1)
    ).first()
    season_rows = session.execute(
        select(Season.year, func.sum(PlayerStatsScored.total_points))
        .join(Season, Season.season_id == PlayerStatsScored.season_id)
        .where(
            PlayerStatsScored.player_id == player_id,
            PlayerStatsScored.week <= Season.regular_season_weeks,
        )
        .group_by(Season.year)
        .order_by(func.sum(PlayerStatsScored.total_points).desc())
    ).all()
    owner_rows = session.execute(
        select(Owner.owner_id, Owner.display_name, func.count())
        .join(Team, Team.owner_id == Owner.owner_id)
        .join(TeamRoster, TeamRoster.team_id == Team.team_id)
        .where(TeamRoster.player_id == player_id)
        .group_by(Owner.owner_id, Owner.display_name)
        .order_by(func.count().desc(), Owner.display_name)
    ).all()

    best_week = None
    if best_week_row is not None:
        year, week, points = best_week_row
        best_week = {
            "season_year": int(year),
            "week": int(week),
            "points": round(float(points), 2),
        }
    best_season = None
    if season_rows:
        year, points = season_rows[0]
        best_season = {"season_year": int(year), "points": round(float(points or 0.0), 2)}
    most_rostered_by = None
    if owner_rows:
        owner_id, display_name, weeks = owner_rows[0]
        most_rostered_by = {
            "owner_id": int(owner_id),
            "display_name": display_name,
            "weeks": int(weeks),
        }

    has_any = bool(best_week or best_season or most_rostered_by or ownership)
    return {
        "player_id": player_id,
        "available": has_any,
        "reason": None if has_any else "no_scored_data",
        "best_week": best_week,
        "best_season": best_season,
        "league_roster_span": {
            "first_rostered_season": ownership["first_rostered_season"] if ownership else None,
            "last_rostered_season": ownership["last_rostered_season"] if ownership else None,
        },
        "most_rostered_by": most_rostered_by,
    }
