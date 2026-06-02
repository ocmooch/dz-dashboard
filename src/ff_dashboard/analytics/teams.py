"""Team-page views (``analytics/teams.py``).

A *team* is one owner's entry in a single season, so every view here is keyed on
``team_id`` and scoped to that team's season. All five are light aggregation over
Phase 1 facts:

* :func:`team_overview` — the season header: record, rank, owner, championship.
  Rank (and its basis) come straight from :func:`compute_standings`, so the team
  page agrees with the standings page by construction.
* :func:`team_roster` — the roster for a given week (latest when ``week`` is
  omitted), with per-player league points where scored. Player points are
  ``null`` (never 0) for unscored seasons / unscored slots.
* :func:`team_schedule` — week-by-week results with the box-score deep-link.
* :func:`team_scoring_trend` — the team's weekly score against the league average
  that week (team scores exist even for pre-2016 seasons, so this is not gated).
* :func:`team_transactions` — the season's moves involving this team.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, PlayerStatsScored
from ff_pipeline.repository.queries import (
    get_player,
    get_season,
    get_team,
    matchups_for_team,
    roster_for_team_week,
    transactions_for_team,
)
from sqlalchemy import func, select

from ff_dashboard.analytics.common import owner_name_map, require_league
from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.matchups import (
    _authoritative_points,
    normalize_position,
    roster_sort_key,
)
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def team_overview(session: Session, team_id: int) -> dict[str, Any] | None:
    """Season header for a team, or ``None`` if no such team (404).

    Record/rank are read from the season's standings so this page and the
    standings page never disagree.
    """
    require_league(session)  # 503 when the pipeline has never run
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover - a team always has its season
        return None

    owners = owner_name_map(session)
    standings = compute_standings(session, team.season_id) or {}
    row = next(
        (r for r in standings.get("rows", []) if r["team_id"] == team_id),
        None,
    )

    return {
        "team_id": team_id,
        "team_name": team.team_name,
        "season_id": season.season_id,
        "season_year": season.year,
        "owner_id": team.owner_id,
        "owner_name": owners.get(team.owner_id),
        "rank": row["rank"] if row else None,
        "rank_basis": standings.get("rank_basis", "computed"),
        "wins": row["wins"] if row else 0,
        "losses": row["losses"] if row else 0,
        "ties": row["ties"] if row else 0,
        "points_for": row["points_for"] if row else 0.0,
        "points_against": row["points_against"] if row else 0.0,
        "final_rank": team.final_rank,
        "made_playoffs": team.made_playoffs,
        "is_champion": season.champion_team_id == team_id,
        "is_scored": season.year in set(seasons_scored(session)),
    }


def team_roster(session: Session, team_id: int, week: int | None) -> dict[str, Any] | None:
    """The team's roster for a week (latest when ``week`` is ``None``).

    Per-player league points are included where the player was scored that week;
    they are ``null`` (never 0) for unscored slots / pre-2016 seasons.
    """
    require_league(session)
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover - a team always has its season
        return None

    # The weeks the team actually played bound the roster stepper.
    weeks_available = sorted(
        int(w)
        for w in session.execute(
            select(func.distinct(Matchup.week)).where(Matchup.team_id == team_id)
        )
        .scalars()
        .all()
    )

    pairs = roster_for_team_week(session, team_id, week)
    # Lay the roster out top-to-bottom the way the box score does: starters
    # (QB, RB, RB, WR, WR, TE, FLEX, K, DST), then bench, then IR.
    pairs = sorted(
        pairs, key=lambda rp: roster_sort_key(rp[0].roster_slot, normalize_position(rp[1].position))
    )
    effective_week = week
    if effective_week is None:
        effective_week = (
            pairs[0][0].week if pairs else (weeks_available[-1] if weeks_available else 0)
        )

    player_ids = [r.player_id for r, _ in pairs]
    scored: dict[int, float] = {}
    if player_ids:
        rows = session.execute(
            select(PlayerStatsScored.player_id, PlayerStatsScored.total_points).where(
                PlayerStatsScored.season_id == season.season_id,
                PlayerStatsScored.week == effective_week,
                PlayerStatsScored.player_id.in_(player_ids),
            )
        ).all()
        scored = {int(pid): float(pts) for pid, pts in rows if pts is not None}

    players = []
    for roster_row, player in pairs:
        # Prefer NFL.com's authoritative per-player points; fall back to the
        # nflverse reconstruction only when the field is absent. Keeps the team
        # page in agreement with the box score (which does the same).
        points = _authoritative_points(roster_row)
        if points is None and player.player_id in scored:
            points = scored[player.player_id]
        players.append(
            {
                "player_id": player.player_id,
                "player_name": player.name_full,
                "position": normalize_position(player.position),
                "nfl_team": player.nfl_team,
                "roster_slot": roster_row.roster_slot,
                "is_starter": bool(roster_row.is_starter),
                "league_points": round(points, 2) if points is not None else None,
                "acquisition_type": roster_row.acquisition_type,
                "acquisition_week": roster_row.acquisition_week,
            }
        )

    return {
        "team_id": team_id,
        "season_year": season.year,
        "week": effective_week,
        "weeks_available": weeks_available,
        "is_scored": season.year in set(seasons_scored(session)),
        "players": players,
    }


def team_schedule(session: Session, team_id: int) -> dict[str, Any] | None:
    """Week-by-week results with the opponent and the box-score deep-link."""
    require_league(session)
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover
        return None

    owners = owner_name_map(session)
    games: list[dict[str, Any]] = []
    for m in matchups_for_team(session, team_id):
        opp = get_team(session, m.opponent_team_id) if m.opponent_team_id is not None else None
        result: str | None = None
        if m.is_win is True:
            result = "W"
        elif m.is_win is False:
            result = "L"
        elif m.team_score is not None and m.opponent_score is not None:
            result = "T"
        margin = (
            round(m.team_score - m.opponent_score, 2)
            if m.team_score is not None and m.opponent_score is not None
            else None
        )
        games.append(
            {
                "matchup_id": m.matchup_id,
                "week": m.week,
                "is_playoff": bool(m.is_playoff),
                "opponent_team_id": m.opponent_team_id,
                "opponent_team_name": opp.team_name if opp is not None else None,
                "opponent_owner_name": owners.get(opp.owner_id) if opp is not None else None,
                "team_score": round(m.team_score, 2) if m.team_score is not None else None,
                "opponent_score": round(m.opponent_score, 2)
                if m.opponent_score is not None
                else None,
                "result": result,
                "margin": margin,
            }
        )

    return {"team_id": team_id, "season_year": season.year, "games": games}


def team_scoring_trend(session: Session, team_id: int) -> dict[str, Any] | None:
    """The team's weekly score vs the league average for that same week.

    Team scores are authoritative from Phase 1 for every season (including the
    pre-2016 player-scoring gap), so this view is not gated on ``is_scored``.
    """
    require_league(session)
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover
        return None

    # League average per week = mean of every team's score that week. Phase 1
    # stores a game as two perspective rows, so averaging all ``team_score`` rows
    # is already a per-team average.
    by_week_scores: dict[int, list[float]] = defaultdict(list)
    by_week_playoff: dict[int, bool] = {}
    for m in session.execute(
        select(Matchup).where(Matchup.season_id == season.season_id)
    ).scalars():
        if m.team_score is not None:
            by_week_scores[m.week].append(m.team_score)
        by_week_playoff[m.week] = by_week_playoff.get(m.week, False) or bool(m.is_playoff)

    own = {m.week: m for m in matchups_for_team(session, team_id)}
    points: list[dict[str, Any]] = []
    for week in sorted(own):
        scores = by_week_scores.get(week, [])
        league_avg = round(sum(scores) / len(scores), 2) if scores else None
        ts = own[week].team_score
        points.append(
            {
                "week": week,
                "team_score": round(ts, 2) if ts is not None else None,
                "league_avg": league_avg,
                "is_playoff": by_week_playoff.get(week, False),
            }
        )

    return {
        "team_id": team_id,
        "season_year": season.year,
        "is_scored": season.year in set(seasons_scored(session)),
        "points": points,
    }


def team_transactions(session: Session, team_id: int) -> dict[str, Any] | None:
    """The season's transactions involving this team (as actor or counterpart)."""
    require_league(session)
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover
        return None

    items: list[dict[str, Any]] = []
    for t in transactions_for_team(session, team_id):
        player = get_player(session, t.player_id) if t.player_id is not None else None
        counterpart = (
            get_team(session, t.counterpart_team_id) if t.counterpart_team_id is not None else None
        )
        items.append(
            {
                "transaction_id": t.transaction_id,
                "transaction_type": t.transaction_type,
                "executed_at": t.executed_at.isoformat() if t.executed_at is not None else None,
                "effective_week": t.effective_week,
                "player_id": t.player_id,
                "player_name": player.name_full if player is not None else None,
                "direction": t.direction,
                "counterpart_team_id": t.counterpart_team_id,
                "counterpart_team_name": counterpart.team_name if counterpart is not None else None,
                "notes": t.notes,
            }
        )

    return {"team_id": team_id, "season_year": season.year, "transactions": items}
