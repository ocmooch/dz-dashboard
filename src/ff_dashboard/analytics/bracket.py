"""Caveated postseason bracket surface.

Phase 1 stores matchup rows, not a fully reliable championship/consolation tree.
This module exposes the proven post-regular-season games grouped by week and
labels consolation only when the source actually distinguishes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup
from ff_pipeline.repository.queries import get_season, get_team
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks, require_league

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


BRACKET_CAVEAT = (
    "Post-regular-season matchups from the source data. Championship versus consolation "
    "structure is shown only when source flags distinguish it."
)


def season_bracket(session: Session, season_id: int) -> dict[str, Any] | None:
    """Return deduped postseason games for ``season_id``; ``None`` when absent."""
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None

    regular_weeks = regular_season_weeks(session, season)
    rows = list(
        session.execute(
            select(Matchup)
            .where(Matchup.season_id == season_id, Matchup.week > regular_weeks)
            .order_by(Matchup.week, Matchup.matchup_id)
        )
        .scalars()
        .all()
    )

    base = {
        "season_id": season_id,
        "season_year": season.year,
        "regular_season_weeks": regular_weeks,
        "caveat": BRACKET_CAVEAT,
    }
    if not rows:
        return {**base, "available": False, "reason": "bracket_unavailable", "weeks": []}

    owners = owner_name_map(session)
    teams: dict[int, Any] = {}
    consolation_distinguished = any(bool(m.is_consolation) for m in rows)

    def team_ref(
        team_id: int | None, score: float | None, is_winner: bool
    ) -> dict[str, Any] | None:
        if team_id is None:
            return None
        team = teams.get(team_id)
        if team is None:
            team = get_team(session, team_id)
            teams[team_id] = team
        return {
            "team_id": team_id,
            "team_name": team.team_name if team is not None else None,
            "owner_id": team.owner_id if team is not None else None,
            "owner_name": owners.get(team.owner_id) if team is not None else None,
            "score": round(score, 2) if score is not None else None,
            "is_winner": is_winner,
        }

    by_week: dict[int, list[dict[str, Any]]] = {}
    seen: set[tuple[int, frozenset[int]]] = set()
    for m in rows:
        pair = frozenset(
            {m.team_id, m.opponent_team_id} if m.opponent_team_id is not None else {m.team_id}
        )
        key = (m.week, pair)
        if key in seen:
            continue
        seen.add(key)

        winner_team_id: int | None = None
        if (
            m.opponent_team_id is not None
            and m.team_score is not None
            and m.opponent_score is not None
        ):
            if m.team_score > m.opponent_score:
                winner_team_id = m.team_id
            elif m.opponent_score > m.team_score:
                winner_team_id = m.opponent_team_id

        is_consolation = bool(m.is_consolation) if consolation_distinguished else None
        by_week.setdefault(m.week, []).append(
            {
                "matchup_id": m.matchup_id,
                "is_playoff": bool(m.is_playoff),
                "is_consolation": is_consolation,
                "team_a": team_ref(m.team_id, m.team_score, winner_team_id == m.team_id),
                "team_b": team_ref(
                    m.opponent_team_id, m.opponent_score, winner_team_id == m.opponent_team_id
                ),
                "winner_team_id": winner_team_id,
            }
        )

    weeks = [{"week": week, "games": games} for week, games in sorted(by_week.items())]
    return {**base, "available": True, "reason": None, "weeks": weeks}
