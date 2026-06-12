"""Matchup & box-score enrichment (``analytics/matchups.py``).

Two views, both built on Phase 1 facts (``matchups`` for the game result,
``team_rosters`` joined to ``player_stats_scored`` for the lineup):

* :func:`week_matchups` — the week's games as *deduped* cards (Phase 1 stores a
  game as two perspective rows; we fold them back into one card with both teams,
  the margin, and the winner, deep-linkable to the box score).
* :func:`box_score` — both lineups with per-player league points + breakdown,
  bench points, the **optimal lineup** and "points left on the bench", and
  projection-vs-actual. Honest about gaps: a starter with no scored row (a DEF
  whose team/week was never scored, or any unscored player) and a season with
  no player scoring are surfaced, never rendered as zero.

The optimal lineup is a real constrained max-assignment, not a heuristic: given
the week's roster and the league's slot eligibility, it is the highest-scoring
*legal* starting lineup. We solve it explicitly (see :func:`solve_optimal`).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from ff_pipeline.repository.models import Matchup, PlayerStatsScored
from ff_pipeline.repository.models import Projection as ProjectionModel
from ff_pipeline.repository.models import ScoringRule as ScoringRuleModel
from ff_pipeline.repository.queries import (
    get_matchup,
    get_season,
    get_team,
    injury_reports_for_week,
    roster_for_team_week,
)
from ff_pipeline.scoring.engine import apply_rules
from ff_pipeline.scoring.rules import ScoringRule as ScoringRuleDataclass
from ff_pipeline.scoring.rules import ScoringRules
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, require_league
from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.season_schedule import season_schedule

# Margin thresholds for the week-matchup flags. Kept here (backend) rather than
# in the SPA so "no metric math in web" holds; the frontend reads the booleans.
CLOSE_MARGIN = 5.0  # a decided/tied game within 5 points
BLOWOUT_MARGIN = 40.0  # a margin of 40+ points

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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

# Slots that hold a team defense. DST is now scored by the pipeline, so a DEF
# starter renders real points like any other slot; the box score only flags a
# DEF slot as a gap (reason ``team_defense_not_scored``) when its scored row is
# genuinely absent for that team/week. Keyed on the *slot*, not the player's
# position, because team-defense rows often carry no position.
DEF_SLOTS = {"DEF", "DST", "D/ST"}


def _authoritative_points(roster_row: Any) -> float | None:
    """The league-awarded points for a roster row, from NFL.com history.

    Phase 1 stores each weekly roster row's authoritative NFL.com fantasy points
    in ``extra_data.nfl_com_points``. This is the real league result: it exists
    even for players nflverse never logged a stat line for (inactive / DNP / bye,
    who legitimately scored 0.0), and the starters' values sum to the matchup's
    ``team_score``. Returns ``None`` only when the field is absent (then the
    caller falls back to the nflverse reconstruction).
    """
    extra = roster_row.extra_data or {}
    value = extra.get("nfl_com_points")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _season_scoring_rules(session: Any, season_id: int) -> ScoringRules:
    """Load scoring rules for a season as a ScoringRules dataclass (read-only)."""
    rows = session.execute(
        select(
            ScoringRuleModel.category,
            ScoringRuleModel.stat_key,
            ScoringRuleModel.points_per_unit,
            ScoringRuleModel.unit_size,
            ScoringRuleModel.threshold_min,
            ScoringRuleModel.threshold_max,
            ScoringRuleModel.flat_points,
        ).where(ScoringRuleModel.season_id == season_id)
    ).all()
    rules = tuple(
        ScoringRuleDataclass(
            category=str(r.category),
            stat_key=str(r.stat_key),
            points_per_unit=float(r.points_per_unit or 0.0),
            unit_size=float(r.unit_size or 1.0),
            threshold_min=float(r.threshold_min) if r.threshold_min is not None else None,
            threshold_max=float(r.threshold_max) if r.threshold_max is not None else None,
            flat_points=float(r.flat_points) if r.flat_points is not None else None,
        )
        for r in rows
    )
    return ScoringRules(season_id=season_id, rules=rules)


def _projected_points_from_stats(
    stats: dict[str, Any] | None, scoring_rules: ScoringRules
) -> float | None:
    """Compute projected fantasy points by applying the season's scoring rules to
    the raw projected-stats dict.  Returns None when stats are absent."""
    if not stats:
        return None
    numeric = {k: float(v) for k, v in stats.items() if isinstance(v, (int, float))}
    if not numeric:
        return None
    return apply_rules(numeric, scoring_rules).total_points


def _batch_projections(
    session: Any, player_ids: list[int], season_year: int, week: int
) -> dict[int, ProjectionModel]:
    """Latest projection row per player for a given season/week, in one query."""
    if not player_ids:
        return {}
    from sqlalchemy import func

    # Subquery: max fetched_at per player for this season/week.
    sub = (
        select(
            ProjectionModel.player_id,
            func.max(ProjectionModel.fetched_at).label("latest"),
        )
        .where(
            ProjectionModel.player_id.in_(player_ids),
            ProjectionModel.season_year == season_year,
            ProjectionModel.week == week,
        )
        .group_by(ProjectionModel.player_id)
        .subquery()
    )
    rows = (
        session.execute(
            select(ProjectionModel).join(
                sub,
                (ProjectionModel.player_id == sub.c.player_id)
                & (ProjectionModel.fetched_at == sub.c.latest),
            )
        )
        .scalars()
        .all()
    )
    return {r.player_id: r for r in rows}


# How much nflverse-credited production, while the league scored 0, counts as a
# genuine discrepancy worth flagging — above the rounding / DST / minor scoring
# differences that routinely separate nflverse from NFL.com (a couple of points).
_UNEXPECTED_ZERO_THRESHOLD = 1.0


def classify_zero(
    points: float | None, opponent: str | None, nflverse_points: float | None
) -> tuple[str | None, str | None]:
    """Explain a 0.0 league result; ``(None, None)`` when no note is warranted.

    Only fires for an authoritative 0.0, returning ``(zero_reason, zero_detail)``:

    * ``"bye"`` — the player's NFL team was on bye that week (the per-week
      ``extra_data.opponent`` is ``"Bye"``). A status reason: they could not play.
    * ``"did_not_play"`` — the team played but the player has no stat line at all
      (no nflverse row): inactive / injury / scratch. Also a status reason.
    * ``"unexpected"`` — the league scored 0 yet nflverse credits material points,
      so the player clearly produced. We surface the discrepancy and a best-guess
      explanation in ``zero_detail`` rather than silently showing a bare 0.
    * ``(None, None)`` — the player played and simply accrued ~0 points; the UI
      should show a plain ``0`` with no explanation.
    """
    if points is None or points != 0.0:
        return None, None
    if (opponent or "").strip().lower() == "bye":
        return "bye", None
    if nflverse_points is None:
        # No stat line and the team played → the player did not suit up.
        return "did_not_play", None
    if abs(nflverse_points) >= _UNEXPECTED_ZERO_THRESHOLD:
        return (
            "unexpected",
            f"nflverse credits {nflverse_points:g} pts but the league scored 0 — "
            "likely a late inactive/scratch or a scoring difference.",
        )
    # A real stat line that nets ~0: they played and scored nothing.
    return None, None


# Roster slots that are not part of the starting lineup. Bench points count; IR /
# reserve / taxi players never enter the optimal lineup and never count as bench
# points (they were not startable that week). "RES" is NFL.com's reserve/IR slot.
BENCH_SLOTS = {"BN", "BE", "BENCH"}
IR_SLOTS = {"IR", "IR2", "TAXI", "NA", "RES"}

# Canonical top-to-bottom display order for any roster: starters in lineup order
# (QB, RB, RB, WR, WR, TE, FLEX, K, DST), then the bench, then IR. Within the
# bench and IR groups players read in the same positional order. One helper so
# the team page and the box score never disagree on how a roster is laid out.
#
# A *position* maps to its family rank; a starting *slot* is ranked the same way,
# with any multi-position (flex) slot slotting in just after TE. Unknowns sort
# last within their group rather than jumping to the top.
_POSITION_RANK: dict[str, int] = {
    "QB": 0,
    "RB": 1,
    "WR": 2,
    "TE": 3,
    "FLEX": 4,
    "K": 5,
    "PK": 5,
    "DEF": 6,
    "DST": 6,
    "D/ST": 6,
}
_UNKNOWN_RANK = 99


def _starter_slot_rank(slot: str | None) -> int:
    """Lineup position of a *starting* slot (QB→RB→WR→TE→FLEX→K→DST)."""
    rank = _POSITION_RANK.get((slot or "").upper())
    if rank is not None:
        return rank
    # Any other recognised starting slot is a flex (R/W/T, W/R, OP, SUPER_FLEX…);
    # a slot we don't recognise at all sorts last among the starters.
    return 4 if slot in SLOT_ELIGIBILITY else _UNKNOWN_RANK


def roster_sort_key(slot: str | None, position: str | None) -> tuple[int, int]:
    """Sort key laying a roster out as starters → bench → IR, each by position.

    Starters are ordered by their *slot* (so the FLEX lands after TE regardless of
    who fills it); bench and IR players are ordered by their *position*.
    """
    if slot in IR_SLOTS:
        return (2, _POSITION_RANK.get((position or "").upper(), _UNKNOWN_RANK))
    if slot in BENCH_SLOTS:
        return (1, _POSITION_RANK.get((position or "").upper(), _UNKNOWN_RANK))
    return (0, _starter_slot_rank(slot))


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


def _team_box(
    session: Session, team_id: int, season: Season, week: int, total_score: float | None
) -> dict[str, Any]:
    """One side of a box score: lineup, bench points, optimal + points-left."""
    team = get_team(session, team_id)
    owners = owner_name_map(session)
    # ``roster_for_team_week`` keys on (team_id, week) only, so guard against a
    # team_id that recurs across seasons by scoping to this matchup's season.
    # Today team_ids are season-unique, so this is defence-in-depth; if it ever
    # drops rows, the upstream roster data is wrong and we want to know.
    roster = roster_for_team_week(session, team_id, week)
    scoped = [(r, p) for r, p in roster if r.season_year == season.year]
    if len(scoped) != len(roster):
        logger.warning(
            "roster for team %s week %s spans seasons; kept %d of %d rows for %s",
            team_id,
            week,
            len(scoped),
            len(roster),
            season.year,
        )
    roster = scoped
    player_ids = [r.player_id for r, _ in roster]
    scored = _scored_points(session, season.season_id, week, player_ids)
    projections = _batch_projections(session, player_ids, season.year, week)
    scoring_rules = _season_scoring_rules(session, season.season_id)
    injuries = injury_reports_for_week(session, season.year, week)

    lineup: list[dict[str, Any]] = []
    starter_points = 0.0
    bench_points = 0.0
    beat_projection_by: float | None = None
    optimal_candidates: list[dict[str, Any]] = []
    starting_slots: list[str] = []

    # Starters (QB, RB, RB, WR, WR, TE, FLEX, K, DST) first, then bench, then IR.
    for roster_row, player in sorted(
        roster,
        key=lambda rp: roster_sort_key(rp[0].roster_slot, rp[1].position),
    ):
        slot = roster_row.roster_slot
        is_starter = (
            bool(roster_row.is_starter) and slot not in BENCH_SLOTS and slot not in IR_SLOTS
        )
        scored_row = scored.get(player.player_id)
        breakdown = scored_row[1] if scored_row is not None else {}

        # Prefer NFL.com's authoritative per-player points (they sum to the team
        # score and cover players nflverse never scored — a real 0.0, not a gap);
        # fall back to the nflverse reconstruction only when the field is absent.
        nflverse_points = scored_row[0] if scored_row is not None else None
        points = _authoritative_points(roster_row)
        if points is None:
            points = nflverse_points
        league_points = round(points, 2) if points is not None else None

        available = points is not None
        reason: str | None = None
        if not available:
            reason = "team_defense_not_scored" if slot in DEF_SLOTS else "no_scored_data"

        # Explain a 0.0 result: a bye / DNP status reason, a plain played-0, or a
        # flagged "unexpected" 0. Uses the per-week opponent ("Bye") + whether the
        # player has any nflverse stat line as evidence of having played.
        opponent = (roster_row.extra_data or {}).get("opponent")
        zero_reason, zero_detail = classify_zero(league_points, opponent, nflverse_points)

        # Projection vs actual. Use the authoritative projected_points when stored;
        # fall back to scoring projected_stats with the season's rules when the
        # pipeline loaded raw stat projections but didn't apply scoring yet.
        projection: float | None = None
        proj_row = projections.get(player.player_id)
        if proj_row is not None:
            if proj_row.projected_points is not None:
                projection = round(float(proj_row.projected_points), 2)
            else:
                computed = _projected_points_from_stats(proj_row.projected_stats, scoring_rules)
                if computed is not None:
                    projection = round(computed, 2)
        projection_delta = (
            round(league_points - projection, 2)
            if league_points is not None and projection is not None
            else None
        )
        team_point_share = (
            round(league_points / total_score, 4)
            if league_points is not None and total_score is not None and total_score > 0
            else None
        )

        injury = injuries.get(player.player_id)
        entry = {
            "roster_slot": slot,
            "player_id": player.player_id,
            "player_name": player.name_full,
            "position": player.position,
            "league_points": league_points,
            "is_starter": is_starter,
            "breakdown": breakdown,
            "projection": projection,
            "projection_delta": projection_delta,
            "team_point_share": team_point_share,
            "available": available,
            "reason": reason,
            "zero_reason": zero_reason,
            "zero_detail": zero_detail,
            "lineup_value": None,
            "injury_status": injury.report_status if injury else None,
            "injury_body_part": injury.report_primary_injury if injury else None,
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
    starter_min = min(
        (
            cast("float", p["league_points"])
            for p in lineup
            if p["is_starter"] and p["league_points"] is not None
        ),
        default=None,
    )
    for entry in lineup:
        points = cast("float | None", entry["league_points"])
        if points is None:
            entry["lineup_value"] = None
        elif entry["is_starter"] and entry["projection_delta"] is not None:
            projection_delta = cast("float", entry["projection_delta"])
            entry["lineup_value"] = "starter_hit" if projection_delta > 0 else "starter_miss"
        elif (
            not entry["is_starter"]
            and entry["roster_slot"] in BENCH_SLOTS
            and starter_min is not None
            and points > starter_min
        ):
            entry["lineup_value"] = "bench_pop"
        else:
            entry["lineup_value"] = "neutral"

    return {
        "team_id": team_id,
        "team_name": period_team_name(team) if team is not None else None,
        "owner_name": owners.get(team.owner_id) if team is not None else None,
        "total_score": round(total_score, 2) if total_score is not None else None,
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
    season has no player-level scoring.
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

    home = _team_box(session, m.team_id, season, m.week, m.team_score)

    away: dict[str, Any] | None = None
    winner_team_id: int | None = None
    if m.opponent_team_id is not None:
        away = _team_box(session, m.opponent_team_id, season, m.week, m.opponent_score)
        # Winner from the authoritative team scores (the real game result).
        if m.team_score is not None and m.opponent_score is not None:
            if m.team_score > m.opponent_score:
                winner_team_id = m.team_id
            elif m.opponent_score > m.team_score:
                winner_team_id = m.opponent_team_id

        # A player cannot legitimately be on both sides of a game; an overlap means
        # duplicated/contaminated roster data upstream (e.g. a non-idempotent load
        # that left a moved player on both his old and new team). Surface it.
        shared = {e["player_id"] for e in home["lineup"]} & {e["player_id"] for e in away["lineup"]}
        if shared:
            logger.warning(
                "matchup %s has %d player(s) rostered on both teams: %s",
                matchup_id,
                len(shared),
                sorted(shared),
            )

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


def _entering_records(session: Session, season: Season, week: int) -> dict[int, dict[str, int]]:
    """Each team's regular-season W-L-T from *before* ``week``, that season.

    One query for the season's prior regular-season games, folded per team — no
    N+1. Playoff/championship weeks are excluded via the schedule model's
    ``regular_weeks``; byes and unplayed weeks don't count.
    """
    reg_weeks = season_schedule(session, season).regular_weeks
    records: dict[int, dict[str, int]] = {}
    rows = session.execute(
        select(
            Matchup.team_id,
            Matchup.is_win,
            Matchup.team_score,
            Matchup.opponent_score,
            Matchup.opponent_team_id,
        ).where(
            Matchup.season_id == season.season_id,
            Matchup.week < week,
            Matchup.week <= reg_weeks,
        )
    ).all()
    for team_id, is_win, team_score, opp_score, opp_team_id in rows:
        if opp_team_id is None:
            continue  # bye, not a game
        rec = records.setdefault(int(team_id), {"wins": 0, "losses": 0, "ties": 0})
        if is_win is True:
            rec["wins"] += 1
        elif is_win is False:
            rec["losses"] += 1
        elif team_score is not None and opp_score is not None and team_score == opp_score:
            rec["ties"] += 1
    return records


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
    entering = _entering_records(session, season, week)

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
            "team_name": period_team_name(team) if team is not None else None,
            "owner_name": owners.get(team.owner_id) if team is not None else None,
            "score": round(score, 2) if score is not None else None,
            "is_winner": is_winner,
            "entering_record": entering.get(team_id, {"wins": 0, "losses": 0, "ties": 0}),
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
                "is_close": margin is not None and margin <= CLOSE_MARGIN,
                "is_blowout": margin is not None and margin >= BLOWOUT_MARGIN,
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
