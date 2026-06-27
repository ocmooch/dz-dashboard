"""Per-team, per-week fantasy scores for a season.

Powers the weekly-scoring beeswarm / intensity heatmap: the spread of a team's
weekly point totals is its boom/bust signature. These are **team** scores
(``Matchup.team_score``), which exist for every played season regardless of the
player-level scoring reconstruction, so this is available wherever matchups are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Team
from ff_pipeline.repository.queries import get_season
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks
from ff_dashboard.analytics.historical_team_names import period_team_name

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def weekly_scores(session: Session, season_id: int) -> dict[str, Any] | None:
    """Every team's weekly scores for a season, or ``None`` if no such season."""
    season = get_season(session, season_id)
    if season is None:
        return None
    reg_weeks = regular_season_weeks(session, season)
    owners = owner_name_map(session)

    teams = list(session.execute(select(Team).where(Team.season_id == season_id)).scalars().all())
    series: dict[int, dict[str, Any]] = {
        t.team_id: {
            "team_id": t.team_id,
            "team_name": period_team_name(t, season.year),
            "owner_id": t.owner_id,
            "owner_name": owners.get(t.owner_id),
            "scores": [],
        }
        for t in teams
    }

    rows = (
        session.execute(
            select(Matchup).where(
                Matchup.season_id == season_id,
                Matchup.team_score.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    for m in sorted(rows, key=lambda x: (x.team_id, x.week or 0)):
        entry = series.get(m.team_id)
        if entry is None:  # pragma: no cover - matchup team always has a Team row
            continue
        entry["scores"].append(
            {"week": m.week, "score": m.team_score, "is_playoff": bool(m.is_playoff)}
        )

    teams_with_scores = [t for t in series.values() if t["scores"]]
    available = len(teams_with_scores) > 0
    return {
        "season_id": season_id,
        "season_year": season.year,
        "regular_season_weeks": reg_weeks,
        "available": available,
        "reason": None if available else "no_matchups",
        "teams": teams_with_scores,
    }
