"""Matchup & box-score enrichment (``analytics/matchups.py``).

Two views, both built on Phase 1 facts (``matchups`` for the game result,
``team_rosters`` joined to ``player_stats_scored`` for the lineup):

* :func:`week_matchups` — the week's games as *deduped* cards (Phase 1 stores a
  game as two perspective rows; we fold them back into one card with both teams,
  the margin, and the winner, deep-linkable to the box score).
* :func:`box_score` — both lineups with per-player league points + breakdown,
  bench points, the **optimal lineup** and "points left on the bench", and
  projection-vs-actual. Honest about gaps: a DST starter with no scored row and
  an unscored (pre-2016) season are surfaced, never rendered as zero.

The optimal lineup is a real constrained max-assignment, not a heuristic: given
the week's roster and the league's slot eligibility, it is the highest-scoring
*legal* starting lineup. We solve it explicitly (see :func:`solve_optimal`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, PlayerStatsScored
from ff_pipeline.repository.queries import (
    get_matchup,
    get_season,
    get_team,
    player_projections,
    roster_for_team_week,
)
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, require_league
from ff_dashboard.analytics.coverage import seasons_scored

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
    from sqlalchemy.orm import Session

# What each *starting* slot is allowed to hold. The slot *counts* are never
# hardcoded — they are read from the actual starting lineup each week (the
# ``roster_slot`` values of the ``is_starter`` rows), so a league that runs two
# flexes or no kicker is handled automatically. Only the eligibility rules (what
# a FLEX accepts, etc.) live here; this is the league's slot configuration the
# roadmap's Q7 asks for, kept in one place rather than scattered through queries.
SLOT_ELIGIBILITY: dict[str, set[str]] = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K", "PK"},
    "DEF": {"DEF", "DST", "D/ST"},
    # Flex variants as Phase 1 stores them (NFL.com uses "R/W/T" and "W/R");
    # the others are common aliases so the solver is robust across platforms.
    "R/W/T": {"RB", "WR", "TE"},
    "W/R/T": {"RB", "WR", "TE"},
    "FLEX": {"RB", "WR", "TE"},
    "W/R": {"WR", "RB"},
    "WR/RB": {"WR", "RB"},
    "W/T": {"WR", "TE"},
    "WR/TE": {"WR", "TE"},
    "Q/W/R/T": {"QB", "RB", "WR", "TE"},
    "OP": {"QB", "RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}

# Slots that hold a team defense — the box score flags these as a known gap when
# unscored (Phase 1's DST scoring is incomplete). Keyed on the *slot*, not the
# player's position, because team-defense rows often carry no position.
DEF_SLOTS = {"DEF", "DST", "D/ST"}

# Roster slots that are not part of the starting lineup. Bench points count; IR /
# reserve / taxi players never enter the optimal lineup and never count as bench
# points (they were not startable that week). "RES" is NFL.com's reserve/IR slot.
BENCH_SLOTS = {"BN", "BE", "BENCH"}
IR_SLOTS = {"IR", "IR2", "TAXI", "NA", "RES"}


def slot_accepts(slot: str | None, position: str | None) -> bool:
    """Whether a player at ``position`` may legally start in ``slot``.

    Unknown slot names fall back to an exact position match, so an unexpected
    slot label never silently makes everyone eligible.
    """
    if slot is None or position is None:
        return False
    eligible = SLOT_ELIGIBILITY.get(slot)
    if eligible is None:
        return slot == position
    return position in eligible


def solve_optimal(players: list[dict[str, Any]], slots: list[str]) -> float:
    """Highest total points from a *legal* assignment of players to slots.

    ``players`` is the candidate pool (each ``{"position", "points"}``; IR
    excluded by the caller); ``slots`` is one entry per starting slot. The set
    of players that can be simultaneously seated forms a *transversal matroid*,
    so the matroid greedy is exact: take players in descending points order and
    keep each one iff it can be seated via a Kuhn augmenting path that preserves
    every player already seated. The result is provably the max-weight lineup.
    """
    order = sorted(range(len(players)), key=lambda i: players[i]["points"], reverse=True)
    slot_owner: list[int | None] = [None] * len(slots)

    def augment(pi: int, visited: list[bool]) -> bool:
        for si, slot in enumerate(slots):
            if visited[si] or not slot_accepts(slot, players[pi]["position"]):
                continue
            visited[si] = True
            owner = slot_owner[si]
            if owner is None or augment(owner, visited):
                slot_owner[si] = pi
                return True
        return False

    total = 0.0
    for pi in order:
        if augment(pi, [False] * len(slots)):
            total += players[pi]["points"]
    return round(total, 2)


def _scored_points(
    session: Session, season_id: int, week: int, player_ids: list[int]
) -> dict[int, tuple[float, dict[str, Any]]]:
    """``player_id -> (total_points, breakdown)`` for one (season, week)."""
    if not player_ids:
        return {}
    rows = session.execute(
        select(
            PlayerStatsScored.player_id,
            PlayerStatsScored.total_points,
            PlayerStatsScored.points_breakdown,
        ).where(
            PlayerStatsScored.season_id == season_id,
            PlayerStatsScored.week == week,
            PlayerStatsScored.player_id.in_(player_ids),
        )
    ).all()
    return {int(pid): (float(pts), bd or {}) for pid, pts, bd in rows}


def _team_box(session: Session, team_id: int, season: Season, week: int) -> dict[str, Any]:
    """One side of a box score: lineup, bench points, optimal + points-left."""
    team = get_team(session, team_id)
    owners = owner_name_map(session)
    roster = roster_for_team_week(session, team_id, week)
    player_ids = [r.player_id for r, _ in roster]
    scored = _scored_points(session, season.season_id, week, player_ids)

    lineup: list[dict[str, Any]] = []
    starter_points = 0.0
    bench_points = 0.0
    beat_projection_by: float | None = None
    optimal_candidates: list[dict[str, Any]] = []
    starting_slots: list[str] = []

    # Starters first, then bench, then IR — a readable, stable lineup order.
    def _rank(slot: str | None) -> int:
        if slot in IR_SLOTS:
            return 2
        if slot in BENCH_SLOTS:
            return 1
        return 0

    for roster_row, player in sorted(roster, key=lambda rp: _rank(rp[0].roster_slot)):
        slot = roster_row.roster_slot
        is_starter = (
            bool(roster_row.is_starter) and slot not in BENCH_SLOTS and slot not in IR_SLOTS
        )
        scored_row = scored.get(player.player_id)
        points = scored_row[0] if scored_row is not None else None
        breakdown = scored_row[1] if scored_row is not None else {}

        available = points is not None
        reason: str | None = None
        if not available:
            reason = "team_defense_not_scored" if slot in DEF_SLOTS else "no_scored_data"

        # Projection vs actual (per starter where a projection exists).
        projection: float | None = None
        projrows = player_projections(session, player.player_id, season.year, week)
        if projrows and projrows[0].projected_points is not None:
            projection = round(float(projrows[0].projected_points), 2)

        entry = {
            "roster_slot": slot,
            "player_id": player.player_id,
            "player_name": player.name_full,
            "position": player.position,
            "league_points": round(points, 2) if points is not None else None,
            "is_starter": is_starter,
            "breakdown": breakdown,
            "projection": projection,
            "available": available,
            "reason": reason,
        }
        lineup.append(entry)

        effective = points if points is not None else 0.0
        if is_starter:
            starter_points += effective
            starting_slots.append(slot or "")
            if projection is not None:
                beat_projection_by = (beat_projection_by or 0.0) + (effective - projection)
        elif slot in BENCH_SLOTS:
            bench_points += effective

        # The optimal lineup may draw from any non-IR player (starter or bench).
        if slot not in IR_SLOTS:
            optimal_candidates.append({"position": player.position, "points": effective})

    optimal_total = solve_optimal(optimal_candidates, starting_slots)
    starter_points = round(starter_points, 2)

    return {
        "team_id": team_id,
        "team_name": team.team_name if team is not None else None,
        "owner_name": owners.get(team.owner_id) if team is not None else None,
        "total_score": None,  # filled by box_score with the authoritative team score
        "starter_points": starter_points,
        "bench_points": round(bench_points, 2),
        "optimal_total": optimal_total,
        "points_left_on_bench": round(optimal_total - starter_points, 2),
        "beat_projection_by": round(beat_projection_by, 2)
        if beat_projection_by is not None
        else None,
        "lineup": lineup,
    }


def box_score(session: Session, matchup_id: int) -> dict[str, Any] | None:
    """Full box score for a matchup, or ``None`` if no such matchup (404).

    Returns an ``available: false`` payload (never zeros) when the matchup's
    season predates player-level scoring (the pre-2016 gap).
    """
    require_league(session)  # 503 when the pipeline has never run
    m = get_matchup(session, matchup_id)
    if m is None:
        return None
    season = get_season(session, m.season_id)
    if season is None:  # pragma: no cover - a matchup always has its season
        return None

    if season.year not in set(seasons_scored(session)):
        return {
            "matchup_id": matchup_id,
            "season_year": season.year,
            "week": m.week,
            "available": False,
            "reason": "season_unscored",
            "is_playoff": bool(m.is_playoff),
        }

    home = _team_box(session, m.team_id, season, m.week)
    home["total_score"] = round(m.team_score, 2) if m.team_score is not None else None

    away: dict[str, Any] | None = None
    winner_team_id: int | None = None
    if m.opponent_team_id is not None:
        away = _team_box(session, m.opponent_team_id, season, m.week)
        away["total_score"] = round(m.opponent_score, 2) if m.opponent_score is not None else None
        # Winner from the authoritative team scores (the real game result).
        if m.team_score is not None and m.opponent_score is not None:
            if m.team_score > m.opponent_score:
                winner_team_id = m.team_id
            elif m.opponent_score > m.team_score:
                winner_team_id = m.opponent_team_id

    return {
        "matchup_id": matchup_id,
        "season_year": season.year,
        "week": m.week,
        "available": True,
        "is_playoff": bool(m.is_playoff),
        "home": home,
        "away": away,
        "winner_team_id": winner_team_id,
    }


def week_matchups(session: Session, season_id: int, week: int) -> dict[str, Any] | None:
    """The week's games as deduped cards, or ``None`` if no such season (404).

    Phase 1 stores each game as two perspective rows; we fold them into one card
    keyed by the unordered team pair, keeping the first row's id as the card's
    box-score deep-link.
    """
    require_league(session)  # 503 when the pipeline has never run
    season = get_season(session, season_id)
    if season is None:
        return None

    rows = list(
        session.execute(
            select(Matchup)
            .where(Matchup.season_id == season_id, Matchup.week == week)
            .order_by(Matchup.matchup_id)
        )
        .scalars()
        .all()
    )
    owners = owner_name_map(session)
    teams: dict[int, Any] = {}

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
            "owner_name": owners.get(team.owner_id) if team is not None else None,
            "score": round(score, 2) if score is not None else None,
            "is_winner": is_winner,
        }

    seen: set[frozenset[int]] = set()
    games: list[dict[str, Any]] = []
    for m in rows:
        pair = frozenset(
            {m.team_id, m.opponent_team_id} if m.opponent_team_id is not None else {m.team_id}
        )
        if pair in seen:
            continue
        seen.add(pair)

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

        margin: float | None = None
        if m.team_score is not None and m.opponent_score is not None:
            margin = round(abs(m.team_score - m.opponent_score), 2)

        games.append(
            {
                "matchup_id": m.matchup_id,
                "is_playoff": bool(m.is_playoff),
                "team_a": team_ref(m.team_id, m.team_score, winner_team_id == m.team_id),
                "team_b": team_ref(
                    m.opponent_team_id, m.opponent_score, winner_team_id == m.opponent_team_id
                ),
                "margin": margin,
                "winner_team_id": winner_team_id,
            }
        )

    return {
        "season_id": season_id,
        "season_year": season.year,
        "week": week,
        "is_scored": season.year in set(seasons_scored(session)),
        "games": games,
    }
