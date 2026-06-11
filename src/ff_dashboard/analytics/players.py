"""Player views: scoring history, ownership, top scorers, season totals,
availability. Mostly light aggregation over Phase 1 facts, with honest gap
handling for unscored seasons and historical availability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import PlayerStatsRaw, PlayerStatsScored, Season
from ff_pipeline.repository.queries import (
    availability_timeline,
    get_player,
    player_availability_for_season,
    player_ownership,
)
from sqlalchemy import select

from ff_dashboard.analytics.common import (
    has_long_td_score_gap,
    long_td_bonus_rules,
    require_league,
)
from ff_dashboard.analytics.coverage import seasons_scored

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def player_scoring(session: Session, player_id: int, season_year: int) -> dict[str, Any] | None:
    """Weekly league points (+ breakdown) for a (player, season).

    Returns ``available: false`` for unscored seasons (e.g. 2010-2015) rather
    than an empty/zero series.
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
            PlayerStatsRaw.stats,
            PlayerStatsScored.season_id,
        )
        .join(Season, Season.season_id == PlayerStatsScored.season_id)
        .join(PlayerStatsRaw, PlayerStatsRaw.stat_id == PlayerStatsScored.stat_id)
        .where(PlayerStatsScored.player_id == player_id, Season.year == season_year)
        .order_by(PlayerStatsScored.week)
    ).all()

    # Determine which long-TD bonus rules are active for this season so we can
    # flag weeks where the nflverse source didn't provide the bonus stats.
    season_id = int(rows[0].season_id) if rows else None
    bonus_keys = long_td_bonus_rules(session, season_id) if season_id is not None else frozenset()

    score_incomplete = False
    weeks: list[dict[str, Any]] = []
    for w, pts, breakdown, raw_stats, _ in rows:
        raw: dict[str, Any] = raw_stats if isinstance(raw_stats, dict) else {}
        gap = has_long_td_score_gap(raw, bonus_keys)
        if gap:
            score_incomplete = True
        weeks.append(
            {
                "week": int(w),
                "points": round(float(pts), 2) if pts is not None else None,
                "breakdown": breakdown or {},
                "score_gap": gap,
            }
        )

    total = round(sum(float(pts) for _, pts, _, _, _ in rows if pts is not None), 2)
    return {
        "player_id": player_id,
        "season_year": season_year,
        "available": True,
        "total_points": total,
        "score_incomplete": score_incomplete,
        "weeks": weeks,
    }


def ownership_timeline(session: Session, player_id: int) -> dict[str, Any] | None:
    """Which league teams owned the player and when (None if no such player)."""
    if get_player(session, player_id) is None:
        return None
    events = player_ownership(session, player_id)
    return {
        "player_id": player_id,
        "events": [
            {
                "team_id": roster.team_id,
                "team_name": team.team_name,
                "season_year": roster.season_year,
                "week": roster.week,
                "roster_slot": roster.roster_slot,
                "acquisition_type": roster.acquisition_type,
            }
            for roster, team in events
        ],
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
