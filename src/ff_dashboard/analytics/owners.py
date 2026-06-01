"""Owner / manager career metrics.

Career numbers key on ``owner_id`` and aggregate the per-season regular-season
records (so they agree with the standings to the decimal), plus championships
and finishes from ``seasons`` / ``teams``.
"""

from __future__ import annotations

from statistics import mean
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Owner, Season, Team
from ff_pipeline.repository.queries import get_owner
from sqlalchemy import select

from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _standings_index(session: Session) -> dict[int, dict[str, Any]]:
    """team_id -> its regular-season standings row, across every season."""
    index: dict[int, dict[str, Any]] = {}
    seasons = session.execute(select(Season)).scalars().all()
    for season in seasons:
        snap = compute_standings(session, season.season_id)
        if snap is None:  # pragma: no cover
            continue
        for row in snap["rows"]:
            index[row["team_id"]] = {**row, "season_year": season.year}
    return index


def owner_seasons(session: Session, owner_id: int) -> list[dict[str, Any]] | None:
    """Season-by-season table for one owner (None if the owner doesn't exist)."""
    if get_owner(session, owner_id) is None:
        return None
    index = _standings_index(session)
    champions = {s.champion_team_id for s in session.execute(select(Season)).scalars().all()}
    teams = list(session.execute(select(Team).where(Team.owner_id == owner_id)).scalars().all())
    season_year: dict[int, int] = {
        int(sid): int(yr)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
    }

    rows: list[dict[str, Any]] = []
    for team in teams:
        srow = index.get(team.team_id, {})
        rows.append(
            {
                "season_id": team.season_id,
                "season_year": season_year.get(team.season_id),
                "team_id": team.team_id,
                "team_name": team.team_name,
                "wins": srow.get("wins", 0),
                "losses": srow.get("losses", 0),
                "ties": srow.get("ties", 0),
                "points_for": srow.get("points_for", 0.0),
                "final_rank": team.final_rank,
                "made_playoffs": team.made_playoffs,
                "is_champion": team.team_id in champions,
            }
        )
    rows.sort(key=lambda r: r["season_year"] or 0)
    return rows


def _career_from_seasons(
    owner_id: int, display_name: str | None, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    finishes = [r["final_rank"] for r in rows if r["final_rank"] is not None]
    championships = [r for r in rows if r["is_champion"]]
    return {
        "owner_id": owner_id,
        "display_name": display_name,
        "seasons_played": len(rows),
        "total_wins": sum(r["wins"] for r in rows),
        "total_losses": sum(r["losses"] for r in rows),
        "total_ties": sum(r["ties"] for r in rows),
        "total_points_for": round(sum(r["points_for"] for r in rows), 2),
        "championships": len(championships),
        "best_finish": min(finishes) if finishes else None,
        "avg_finish": round(mean(finishes), 2) if finishes else None,
    }


def owner_career(session: Session, owner_id: int) -> dict[str, Any] | None:
    """Career aggregate + trophy case for one owner (None if not found)."""
    owner = get_owner(session, owner_id)
    if owner is None:
        return None
    rows = owner_seasons(session, owner_id) or []
    career = _career_from_seasons(owner_id, owner.display_name, rows)
    trophy_case = [
        {
            "season_year": r["season_year"],
            "team_name": r["team_name"],
            "finish": r["final_rank"],
            "is_champion": r["is_champion"],
        }
        for r in rows
        if r["is_champion"] or (r["final_rank"] is not None and r["final_rank"] <= 3)
    ]
    return {**career, "trophy_case": trophy_case}


def list_owners_career(session: Session) -> list[dict[str, Any]]:
    """Career line for every owner, ranked by championships then wins."""
    owners = list(session.execute(select(Owner)).scalars().all())
    by_owner: dict[int, list[dict[str, Any]]] = {}
    for o in owners:
        by_owner[o.owner_id] = owner_seasons(session, o.owner_id) or []
    careers = [
        _career_from_seasons(o.owner_id, o.display_name, by_owner[o.owner_id]) for o in owners
    ]
    careers.sort(key=lambda c: (-c["championships"], -c["total_wins"], -c["total_points_for"]))
    return careers


def owner_trajectory(session: Session, owner_id: int) -> list[dict[str, Any]] | None:
    """Final rank + points-for per season, for the trajectory chart."""
    rows = owner_seasons(session, owner_id)
    if rows is None:
        return None
    return [
        {
            "season_year": r["season_year"],
            "final_rank": r["final_rank"],
            "points_for": r["points_for"],
        }
        for r in rows
    ]
