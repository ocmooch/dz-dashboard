"""Manager lineup efficiency ("Manager IQ") for a season.

The fantasy-native skill signal: what fraction of a team's *optimal* points its
manager actually started. Reuses the canonical optimal-lineup solver per team-week
(``matchups._team_box``) so this can never disagree with the box score. Bounded to
one season (about teams * weeks box computations) and cached at the endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Team
from ff_pipeline.repository.queries import get_season
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks
from ff_dashboard.analytics.game_state import BENCH_OR_RESERVE, is_pending_extra
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.matchups import _team_box
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
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
    pending = pending_team_weeks(session, season_id)
    for t in teams:
        lw = team_lineup_weeks(session, season, t.team_id, reg_weeks, pending)
        captured, optimal, weeks = lw["captured"], lw["optimal"], lw["weeks"]
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


def pending_team_weeks(session: Session, season_id: int) -> set[tuple[int, int]]:
    """``(team_id, week)`` of every unfinished (unscored) week: counted nowhere (D3 rule)."""
    rows = session.execute(
        select(Matchup.team_id, Matchup.week, Matchup.extra_data).where(
            Matchup.season_id == season_id
        )
    )
    return {(int(t), int(w)) for t, w, extra in rows if is_pending_extra(extra)}


def team_lineup_weeks(
    session: Session,
    season: Season,
    team_id: int,
    through_week: int,
    pending: set[tuple[int, int]],
) -> dict[str, Any]:
    """Started vs optimal points over weeks 1..``through_week`` for one team.

    Only weeks with a real, solvable lineup count (an empty/unscored week has optimal 0 and is
    an honest gap, never 0). A pending week is skipped. ``uncertain_weeks`` lists counted weeks
    where a bench slot may really be IR (``bench_or_reserve``): the solver may start that player.
    """
    captured = optimal = 0.0
    weeks = 0
    uncertain: list[int] = []
    for wk in range(1, through_week + 1):
        if (team_id, wk) in pending:
            continue
        box = _team_box(session, team_id, season, wk, None)
        opt = box.get("optimal_total") or 0.0
        if opt <= 0:
            continue
        captured += box.get("starter_points") or 0.0
        optimal += opt
        weeks += 1
        if any(e.get("slot_note") == BENCH_OR_RESERVE for e in box.get("lineup") or []):
            uncertain.append(wk)
    return {"captured": captured, "optimal": optimal, "weeks": weeks, "uncertain_weeks": uncertain}


def season_potential_points(
    session: Session, season_id: int, through_week: int | None = None
) -> dict[int, dict[str, Any]]:
    """``{team_id: {computed, official, weeks, uncertain_weeks}}`` for a season's regular season.

    ``computed`` is the BFF's optimal-lineup total, one method for every era (``01`` §3, row 101);
    ``None`` when no week is solvable (a gap, never 0). ``official`` is the platform's own
    figure (Sleeper ``ppts``), a cross-check that is never mixed into ``computed``.
    """
    season = get_season(session, season_id)
    if season is None:
        return {}
    reg_weeks = regular_season_weeks(session, season)
    last = min(through_week, reg_weeks) if through_week is not None else reg_weeks
    pending = pending_team_weeks(session, season_id)
    out: dict[int, dict[str, Any]] = {}
    for t in session.scalars(select(Team).where(Team.season_id == season_id)):
        lw = team_lineup_weeks(session, season, t.team_id, last, pending)
        ppts = (t.extra_data or {}).get("ppts")
        out[int(t.team_id)] = {
            "computed": round(lw["optimal"], 2) if lw["weeks"] else None,
            "official": round(float(ppts), 2) if ppts is not None else None,
            "weeks": lw["weeks"],
            "uncertain_weeks": lw["uncertain_weeks"],
        }
    return out
