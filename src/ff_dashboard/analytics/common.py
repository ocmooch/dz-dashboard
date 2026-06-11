"""Helpers shared across analytics modules.

Kept deliberately small: league resolution (the dashboard serves a single
league), name lookups, and the regular-season-week helper that every metric
needs so no view ever hardcodes 14 or 17 weeks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.api.errors import service_unavailable
from ff_pipeline.repository.models import League, Owner, ScoringRule, Season, Team
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Stat keys that require play-by-play analysis (nflverse M7 gap).
# nflverse load_player_stats() never populates these; they are absent from
# every player_stats_raw row, so the scoring engine silently scores them as 0.
# Any player-week where these would be non-zero has an understated total.
LONG_TD_BONUS_STAT_KEYS: frozenset[str] = frozenset(
    {
        "passing_yards_bonus_long_td_40",
        "passing_yards_bonus_long_td_50",
        "rushing_yards_bonus_long_td_40",
        "rushing_yards_bonus_long_td_50",
        "receiving_yards_bonus_long_td_40",
        "receiving_yards_bonus_long_td_50",
    }
)

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


def team_owner_map(session: Session) -> dict[int, int]:
    """team_id -> owner_id for every team (career/rivalry metrics key on owner)."""
    rows = session.execute(select(Team.team_id, Team.owner_id)).all()
    return {int(tid): int(oid) for tid, oid in rows}


def long_td_bonus_rules(session: Session, season_id: int) -> frozenset[str]:
    """Which long-TD-bonus stat keys have scoring rules for this season.

    Returns the intersection of ``LONG_TD_BONUS_STAT_KEYS`` with the
    season's actual scoring rules.  An empty set means the league doesn't
    award long-TD bonuses, and no gap indicator is needed.
    """
    present = frozenset(
        session.execute(
            select(ScoringRule.stat_key).where(
                ScoringRule.season_id == season_id,
                ScoringRule.stat_key.in_(list(LONG_TD_BONUS_STAT_KEYS)),
            )
        )
        .scalars()
        .all()
    )
    return present


def has_long_td_score_gap(raw_stats: dict[str, Any], bonus_rule_keys: frozenset[str]) -> bool:
    """Return True when a player-week score may be understated by long-TD bonuses.

    Requires that:
    * the season has at least one long-TD bonus scoring rule (``bonus_rule_keys`` non-empty),
    * the player had at least one TD that week (so a long-TD bonus is plausible), and
    * at least one long-TD bonus stat key is absent from the raw stats dict
      (confirming the source never provided it, not that the stat was zero).
    """
    if not bonus_rule_keys:
        return False
    has_td = (
        float(raw_stats.get("receiving_tds") or 0) > 0
        or float(raw_stats.get("rushing_tds") or 0) > 0
        or float(raw_stats.get("passing_tds") or 0) > 0
    )
    if not has_td:
        return False
    return any(k not in raw_stats for k in bonus_rule_keys)
