"""Standings, streaks, and the standings-over-time timeline.

Record/PF/PA are regular-season only (weeks 1..regular_season_weeks). The
standings rank is computed wins-desc then points-for-desc (the league's
documented tiebreaker). Where Phase 1 reconstructed an authoritative
``teams.final_rank`` for the full season, we order by that instead — it is the
NFL.com truth, including any historical tiebreak we deliberately do not
re-implement — and flag the difference so the UI can be honest about it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Team
from ff_pipeline.repository.queries import get_season
from sqlalchemy import select

from ff_dashboard.analytics.common import (
    CONSISTENT_TIEBREAK_SINCE,
    owner_name_map,
    regular_season_weeks,
)

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
    from sqlalchemy.orm import Session


def _result(team_score: float | None, opp_score: float | None, is_win: bool | None) -> str | None:
    """W / L / T for a played game, or None for a bye / unplayed week."""
    if is_win is True:
        return "W"
    if is_win is False:
        return "L"
    if team_score is not None and opp_score is not None:
        return "T"
    return None


def _current_streak(results: list[str]) -> dict[str, Any]:
    """Trailing run of the same result in week order (e.g. {'result':'W','length':3})."""
    if not results:
        return {"result": None, "length": 0}
    last = results[-1]
    length = 0
    for r in reversed(results):
        if r == last:
            length += 1
        else:
            break
    return {"result": last, "length": length}


def compute_standings(
    session: Session, season_id: int, through_week: int | None = None
) -> dict[str, Any] | None:
    """Standings for a season (optionally as-of a week). ``None`` if no season."""
    season = get_season(session, season_id)
    if season is None:
        return None

    reg_weeks = regular_season_weeks(session, season)
    upper = reg_weeks if through_week is None else min(through_week, reg_weeks)
    is_full_season = through_week is None or through_week >= reg_weeks

    teams = list(session.execute(select(Team).where(Team.season_id == season_id)).scalars().all())
    team_by_id = {t.team_id: t for t in teams}
    owners = owner_name_map(session)

    matchups = list(
        session.execute(
            select(Matchup)
            .where(Matchup.season_id == season_id, Matchup.week <= upper)
            .order_by(Matchup.week)
        )
        .scalars()
        .all()
    )

    agg: dict[int, dict[str, Any]] = {
        t.team_id: {"wins": 0, "losses": 0, "ties": 0, "pf": 0.0, "pa": 0.0, "results": []}
        for t in teams
    }
    for m in matchups:
        row = agg.get(m.team_id)
        if row is None:
            continue
        res = _result(m.team_score, m.opponent_score, m.is_win)
        if res == "W":
            row["wins"] += 1
        elif res == "L":
            row["losses"] += 1
        elif res == "T":
            row["ties"] += 1
        if res is not None:
            row["results"].append(res)
        row["pf"] += m.team_score or 0.0
        row["pa"] += m.opponent_score or 0.0

    rows: list[dict[str, Any]] = []
    for team_id, a in agg.items():
        team = team_by_id[team_id]
        games = a["wins"] + a["losses"] + a["ties"]
        rows.append(
            {
                "team_id": team_id,
                "team_name": team.team_name,
                "owner_id": team.owner_id,
                "owner_name": owners.get(team.owner_id),
                "wins": a["wins"],
                "losses": a["losses"],
                "ties": a["ties"],
                "points_for": round(a["pf"], 2),
                "points_against": round(a["pa"], 2),
                "win_pct": round((a["wins"] + 0.5 * a["ties"]) / games, 4) if games else 0.0,
                "streak": _current_streak(a["results"]),
                "final_rank": team.final_rank,
            }
        )

    use_final = is_full_season and all(r["final_rank"] is not None for r in rows) and bool(rows)
    if use_final:
        rows.sort(key=lambda r: r["final_rank"])
        rank_basis = "final_rank"
    else:
        rows.sort(key=lambda r: (-r["wins"], -r["points_for"]))
        rank_basis = "computed"
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    tiebreak_caveat = rank_basis == "computed" and season.year < CONSISTENT_TIEBREAK_SINCE

    return {
        "season_id": season_id,
        "season_year": season.year,
        "through_week": upper,
        "regular_season_weeks": reg_weeks,
        "rank_basis": rank_basis,
        "tiebreak_caveat": tiebreak_caveat,
        "rows": rows,
    }


def standings_timeline(session: Session, season_id: int) -> dict[str, Any] | None:
    """Rank (computed) and cumulative points-for per team per regular-season week."""
    season = get_season(session, season_id)
    if season is None:
        return None
    reg_weeks = regular_season_weeks(session, season)

    teams = list(session.execute(select(Team).where(Team.season_id == season_id)).scalars().all())
    owners = owner_name_map(session)
    series: dict[int, dict[str, Any]] = {
        t.team_id: {
            "team_id": t.team_id,
            "team_name": t.team_name,
            "owner_id": t.owner_id,
            "owner_name": owners.get(t.owner_id),
            "points": [],
        }
        for t in teams
    }

    for week in range(1, reg_weeks + 1):
        snap = compute_standings(session, season_id, through_week=week)
        if snap is None:  # pragma: no cover - season existence already checked
            continue
        # Recompute rank by the computed basis for a consistent climbing chart.
        ordered = sorted(snap["rows"], key=lambda r: (-r["wins"], -r["points_for"]))
        for rank, r in enumerate(ordered, start=1):
            series[r["team_id"]]["points"].append(
                {"week": week, "rank": rank, "points_for": r["points_for"]}
            )

    return {
        "season_id": season_id,
        "season_year": season.year,
        "regular_season_weeks": reg_weeks,
        "teams": list(series.values()),
    }


def season_summary(session: Session, season: Season) -> dict[str, Any]:
    """Champion / runner-up / last-place names + week counts for a season."""
    owners = owner_name_map(session)
    team_rows = session.execute(
        select(Team.team_id, Team.team_name, Team.owner_id).where(
            Team.season_id == season.season_id
        )
    ).all()
    name_by_team = {int(tid): tname for tid, tname, _ in team_rows}
    owner_by_team = {int(tid): int(oid) for tid, _, oid in team_rows}

    def label(team_id: int | None) -> dict[str, Any] | None:
        if team_id is None:
            return None
        return {
            "team_id": team_id,
            "team_name": name_by_team.get(team_id),
            "owner_id": owner_by_team.get(team_id),
            "owner_name": owners.get(owner_by_team.get(team_id, -1)),
        }

    return {
        "season_id": season.season_id,
        "season_year": season.year,
        "status": season.status,
        "regular_season_weeks": season.regular_season_weeks,
        "playoff_weeks": season.playoff_weeks,
        "champion": label(season.champion_team_id),
        "runner_up": label(season.runner_up_team_id),
        "last_place": label(season.last_place_team_id),
    }
