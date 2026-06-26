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
from sqlalchemy import select, text

from ff_dashboard.analytics.common import (
    CONSISTENT_TIEBREAK_SINCE,
    owner_name_map,
    regular_season_weeks,
)
from ff_dashboard.analytics.historical_team_names import (
    period_team_name,
    period_team_name_by_slot,
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

    # conference_id exists in the DB teams table but may not be mapped in the
    # current ff_pipeline Team ORM model — read via raw SQL so we degrade
    # gracefully if the column is absent rather than crashing.
    team_conf_ids: dict[int, int | None] = {}
    try:
        for tid, cid in session.execute(
            text("SELECT team_id, conference_id FROM teams WHERE season_id = :sid"),
            {"sid": season_id},
        ):
            team_conf_ids[int(tid)] = int(cid) if cid is not None else None
    except Exception:
        pass

    conf_names: dict[int, str | None] = {}
    try:
        for cid, name in session.execute(
            text("SELECT conference_id, name FROM season_conferences WHERE season_id = :sid"),
            {"sid": season_id},
        ):
            conf_names[int(cid)] = name
    except Exception:
        pass

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
        conf_id = team_conf_ids.get(team_id)
        rows.append(
            {
                "team_id": team_id,
                "team_name": period_team_name(team, season.year),
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
                "conference_id": conf_id,
                "conference_name": conf_names.get(conf_id) if conf_id is not None else None,
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

    # Mark the season's Sacko (toilet-bowl loser / recorded last place) so the
    # full-season table can carry the 💩 anti-trophy. Only resolved for a complete
    # season — through a week the bracket hasn't happened yet, there is no Sacko —
    # which also keeps the per-week timeline sweep from paying for the classifier.
    # Imported lazily: ``bracket`` → ``conferences`` → ``standings`` is a cycle.
    sacko_team_id: int | None = None
    if is_full_season:
        from ff_dashboard.analytics.bracket import postseason_classification

        sacko_team_id = (postseason_classification(session, season_id).get("sacko") or {}).get(
            "team_id"
        )
    for r in rows:
        r["is_sacko"] = sacko_team_id is not None and r["team_id"] == sacko_team_id

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


def all_play_index(
    session: Session, season_id: int, through_week: int | None = None
) -> dict[int, dict[str, float | int]]:
    """Team all-play record for regular-season weeks.

    For each week, every played team is compared against every other played
    team's score. This measures schedule luck without player-level data.
    """
    season = get_season(session, season_id)
    if season is None:
        return {}
    reg_weeks = regular_season_weeks(session, season)
    upper = reg_weeks if through_week is None else min(through_week, reg_weeks)
    rows = session.execute(
        select(Matchup.team_id, Matchup.week, Matchup.team_score).where(
            Matchup.season_id == season_id,
            Matchup.week <= upper,
            Matchup.team_score.is_not(None),
            Matchup.opponent_team_id.is_not(None),
        )
    ).all()
    by_week: dict[int, list[tuple[int, float]]] = {}
    for team_id, week, score in rows:
        by_week.setdefault(int(week), []).append((int(team_id), float(score)))

    index: dict[int, dict[str, float | int]] = {}
    for played in by_week.values():
        if len(played) < 2:
            continue
        for team_id, score in played:
            rec = index.setdefault(team_id, {"wins": 0, "losses": 0, "ties": 0, "games": 0})
            for other_id, other_score in played:
                if other_id == team_id:
                    continue
                rec["games"] += 1
                if score > other_score:
                    rec["wins"] += 1
                elif score < other_score:
                    rec["losses"] += 1
                else:
                    rec["ties"] += 1
    for rec in index.values():
        games = int(rec["games"])
        rec["win_pct"] = (
            round((float(rec["wins"]) + 0.5 * float(rec["ties"])) / games, 4) if games else 0.0
        )
    return index


def standings_insights(
    session: Session, season_id: int, through_week: int | None = None
) -> dict[str, Any] | None:
    """Schedule-luck standings insight using all-play expected wins."""
    standings = compute_standings(session, season_id, through_week)
    if standings is None:
        return None
    rows = standings["rows"]
    if not rows:
        return {
            "season_id": season_id,
            "season_year": standings["season_year"],
            "through_week": standings["through_week"],
            "available": False,
            "reason": "no_standings_rows",
            "teams": [],
        }

    all_play = all_play_index(session, season_id, standings["through_week"])
    if not all_play:
        return {
            "season_id": season_id,
            "season_year": standings["season_year"],
            "through_week": standings["through_week"],
            "available": False,
            "reason": "no_completed_matchups",
            "teams": [],
        }

    pf_rank = {
        r["team_id"]: i for i, r in enumerate(sorted(rows, key=lambda x: -x["points_for"]), start=1)
    }
    teams: list[dict[str, Any]] = []
    for r in rows:
        games = r["wins"] + r["losses"] + r["ties"]
        ap = all_play.get(r["team_id"])
        if ap is None or not games:
            continue
        all_play_pct = float(ap["win_pct"])
        actual_wins = r["wins"] + 0.5 * r["ties"]
        expected_wins = all_play_pct * games
        teams.append(
            {
                "team_id": r["team_id"],
                "owner_id": r["owner_id"],
                "owner_name": r["owner_name"],
                "team_name": r["team_name"],
                "actual_wins": round(actual_wins, 2),
                "all_play_win_pct": round(all_play_pct, 4),
                "expected_wins": round(expected_wins, 2),
                "luck_delta": round(actual_wins - expected_wins, 2),
                "points_for_rank": pf_rank[r["team_id"]],
                "standings_rank": r["rank"],
            }
        )
    teams.sort(key=lambda r: r["luck_delta"], reverse=True)
    # The single most-robbed (lowest luck_delta) and most-blessed (highest) team
    # of the season — the voiced headline picks. Chosen server-side so the
    # frontend stays free of metric math (hard rule). Ties break to the lower
    # team_id for a stable, reproducible pick.
    most_blessed = max(teams, key=lambda t: (t["luck_delta"], -t["team_id"])) if teams else None
    most_robbed = min(teams, key=lambda t: (t["luck_delta"], t["team_id"])) if teams else None
    return {
        "season_id": season_id,
        "season_year": standings["season_year"],
        "through_week": standings["through_week"],
        "available": bool(teams),
        "reason": None if teams else "no_completed_matchups",
        "most_robbed": most_robbed,
        "most_blessed": most_blessed,
        "teams": teams,
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
            "team_name": period_team_name(t, season.year),
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
        select(Team.team_id, Team.team_name, Team.team_abbrev, Team.owner_id).where(
            Team.season_id == season.season_id
        )
    ).all()
    name_by_team = {
        int(tid): period_team_name_by_slot(season.year, abbrev, tname)
        for tid, tname, abbrev, _ in team_rows
    }
    owner_by_team = {int(tid): int(oid) for tid, _, _, oid in team_rows}

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
