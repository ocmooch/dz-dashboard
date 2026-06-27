"""Manager lineup efficiency ("Manager IQ") for a season.

The fantasy-native skill signal: what fraction of a team's *optimal* points its
manager actually started. Reuses the canonical optimal-lineup solver per team-week
(``matchups._team_box``) so this can never disagree with the box score. Bounded to
one season (about teams * weeks box computations) and cached at the endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Team
from ff_pipeline.repository.queries import get_season
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.matchups import _team_box
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def season_efficiency(session: Session, season_id: int) -> dict[str, Any] | None:
    """Per-team captured/optimal points and efficiency for a season, or ``None``."""
    season = get_season(session, season_id)
    if season is None:
        return None
    reg_weeks = regular_season_weeks(session, season)
    owners = owner_name_map(session)

    standings = compute_standings(session, season_id, through_week=reg_weeks)
    pf_by_team: dict[int, float] = (
        {r["team_id"]: r["points_for"] for r in standings["rows"]} if standings else {}
    )

    teams = list(session.execute(select(Team).where(Team.season_id == season_id)).scalars().all())
    out: list[dict[str, Any]] = []
    for t in teams:
        captured = 0.0
        optimal = 0.0
        weeks = 0
        for wk in range(1, reg_weeks + 1):
            box = _team_box(session, t.team_id, season, wk, None)
            opt = box.get("optimal_total") or 0.0
            started = box.get("starter_points") or 0.0
            # Only weeks with a real, solvable lineup contribute (an empty/unscored
            # week has optimal 0 and is an honest gap, never a 0% efficiency).
            if opt > 0:
                captured += started
                optimal += opt
                weeks += 1
        if weeks == 0 or optimal <= 0:
            continue
        out.append(
            {
                "team_id": t.team_id,
                "owner_id": t.owner_id,
                "owner_name": owners.get(t.owner_id),
                "team_name": period_team_name(t, season.year),
                "captured": round(captured, 2),
                "optimal": round(optimal, 2),
                "efficiency_pct": round(captured / optimal, 4),
                "points_for": pf_by_team.get(t.team_id, 0.0),
                "weeks": weeks,
            }
        )

    available = len(out) > 0
    return {
        "season_id": season_id,
        "season_year": season.year,
        "available": available,
        "reason": None if available else "no_solvable_lineups",
        "teams": out,
    }
