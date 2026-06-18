"""Draft board + pick-value analysis (``analytics/draft.py``).

A draft pick is a ``transactions`` row with ``transaction_type='draft'`` (Phase 1
design). The schema carries no explicit round/overall column, so pick order is
recovered from ``executed_at`` (ascending, ``transaction_id`` breaking ties): the
*n*-th draft transaction of a season is overall pick *n*. Round and slot follow
from the number of teams that drafted that season.

Three views, all built on those picks joined to ``players`` and to the player's
regular-season scored total:

* :func:`draft_board` — round-by-round picks per team for a season.
* :func:`draft_value` — for each pick, ``value = season_points - expected`` where
  *expected* is the league-wide average regular-season points of players taken
  **near** that overall slot, computed from every captured draft in history. A
  **steal** outscores its slot (positive value); a **bust** falls short
  (negative). The metric definition travels in the payload so the UI can show it.
* :func:`best_worst_picks` — the best/worst picks ever, for the records book.

Honest about gaps, *and* honest about real zeroes. A season with **no** captured
draft transactions returns ``available: false`` rather than an invented board. A
pick whose player has no scored total is then classified rather than lumped
together (see :func:`_classify_pick_scoring`):

* an unscored season → ``season_unscored``;
* a DST with no stats → ``team_defense_not_scored`` (a defense can never have a
  legitimate season-long 0, so this is always a data gap, never a real zero);
* a player with raw stats but no scored row → ``player_unscored``;
* a never-matched player (no canonical id) → ``player_identity_unresolved``;
* a real, fully-identified player who was **drafted but never played all season**
  (season-long injury / IR, e.g. a torn ACL in camp) → a genuine ``0.0`` shown
  *on* the board with ``zero_reason="did_not_play_season"`` and a note, so the
  pick ranks as the bust it was instead of vanishing behind a gap.

The first four stay ``available: false`` (no invented value); the last is a real
score. A scored pick whose overall slot has no historical neighbours to anchor an
expectation is ``available: false`` (``insufficient_history``) for *value* only.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import fmean, pstdev
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import (
    Player,
    PlayerStatsRaw,
    PlayerStatsScored,
    Season,
    Team,
    TeamRoster,
    Transaction,
)
from ff_pipeline.repository.queries import get_season
from sqlalchemy import distinct, func, select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks, require_league
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.matchups import BENCH_SLOTS, IR_SLOTS, _identity_cluster_members
from ff_dashboard.analytics.weighting import positional_weight, weighted_impact

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# How "near" an overall slot we pool historical picks when estimating the
# expected points for that slot. A small symmetric window borrows strength from
# neighbouring picks without smearing a 1st-rounder's bar into a 10th-rounder's.
VALUE_SLOT_WINDOW = 2

VALUE_DEFINITION = (
    "Pick value = a player's regular-season fantasy points that season minus the "
    "league-wide average for players drafted within "
    f"±{VALUE_SLOT_WINDOW} of the same overall slot (computed from every "
    "captured draft). Positive = a steal (outscored its slot); negative = a bust."
)

# --- Composite "draft impact" weighting -------------------------------------
# impact = normalized_value * cost_weight * opportunity_weight. These are an *editable
# proposal* — named, documented knobs, not opaque magic numbers; tune them
# freely. See docs/plans/P-draft-impact-model.md for the rationale and a worked
# example (2015 Cruz the bench bust vs 2016 Gordon the IR bust).
COST_FLOOR = 0.30  # capital still "spent" on the very last pick (late picks aren't free)
COST_CURVE = 1.0  # curvature of the capital decay (1 = linear, >1 = front-loaded)
OPP_BENCH_WEIGHT = 1.0  # max bust amplification for a full season carried on the active bench
OPP_IR_WEIGHT = 0.25  # max bust amplification for a full season stashed on IR / reserve
WEIGHTED_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})
LEADERBOARD_LIMIT = 9

IMPACT_DEFINITION = (
    "Draft impact = position-normalized pick value scaled by how the pick was spent "
    "and carried. QB, RB, WR, and TE are compared with their own position before "
    "ranking together. An "
    "early-round bust (or a late-round steal) weighs more than the same value late "
    "(or early); and a bust carried all year on the active bench costs more than "
    "one stashed on IR / reserve. Opportunity cost amplifies weighted busts only. "
    "Positive impact = weighted steal; negative impact = weighted bust."
)


def _season_points(session: Session, season: Season, player_ids: set[int]) -> dict[int, float]:
    """Drafted ``player_id -> regular-season points``, resolving identity clusters.

    A draft transaction owns the canonical/roster-side id, while scored rows can
    still live on a linked source member. For each week prefer the drafted id's
    row and otherwise take the first linked member row. This prevents both gaps
    (Mike Williams 2019) and double counting when both sides are populated.
    """
    if not player_ids:
        return {}
    reg = regular_season_weeks(session, season)
    cluster_members = _identity_cluster_members(session, sorted(player_ids))
    lookup_ids = sorted({member for members in cluster_members.values() for member in members})
    rows = session.execute(
        select(
            PlayerStatsScored.player_id,
            PlayerStatsScored.week,
            func.sum(PlayerStatsScored.total_points),
        )
        .where(
            PlayerStatsScored.season_id == season.season_id,
            PlayerStatsScored.week <= reg,
            PlayerStatsScored.player_id.in_(lookup_ids),
            PlayerStatsScored.total_points.is_not(None),
        )
        .group_by(PlayerStatsScored.player_id, PlayerStatsScored.week)
    ).all()
    normalized_rows = [
        (int(pid), int(week), float(pts)) for pid, week, pts in rows if pts is not None
    ]
    return _resolved_cluster_points(normalized_rows, cluster_members, reg)


def _resolved_cluster_points(
    rows: list[tuple[int, int, float]],
    cluster_members: dict[int, list[int]],
    reg_weeks: int,
) -> dict[int, float]:
    """Resolve weekly member rows to each drafted identity without double counting."""
    by_member_week = {
        (int(pid), int(week)): float(pts) for pid, week, pts in rows if pts is not None
    }
    out: dict[int, float] = {}
    for player_id, members in cluster_members.items():
        weekly: list[float] = []
        for week in range(1, reg_weeks + 1):
            for member_id in members:
                points = by_member_week.get((member_id, week))
                if points is not None:
                    weekly.append(points)
                    break
        if weekly:
            out[player_id] = sum(weekly)
    return out


def _players_with_raw(session: Session, season: Season, player_ids: set[int]) -> set[int]:
    """``player_id`` of everyone with at least one raw stat row that season.

    Presence of a raw line means the player suited up at least once; its absence
    across a *scored* season is what separates a genuine season-long non-play
    (a real 0) from a player who simply hasn't been scored yet.
    """
    if not player_ids:
        return set()
    cluster_members = _identity_cluster_members(session, sorted(player_ids))
    lookup_ids = sorted({member for members in cluster_members.values() for member in members})
    rows = (
        session.execute(
            select(distinct(PlayerStatsRaw.player_id)).where(
                PlayerStatsRaw.season_year == season.year,
                PlayerStatsRaw.player_id.in_(lookup_ids),
            )
        )
        .scalars()
        .all()
    )
    raw_members = {int(pid) for pid in rows}
    return {
        player_id
        for player_id, members in cluster_members.items()
        if raw_members.intersection(members)
    }


def _drafted_roster_slots(
    session: Session, season: Season, player_ids: set[int]
) -> dict[int, set[str]]:
    """Per drafted player, the distinct roster slots they occupied that season.

    Used only to phrase the did-not-play note — held on injured reserve vs
    carried on the active bench — and is empty when a player was never rostered
    after being drafted. (The same slot signal feeds the deferred opportunity-
    cost weighting; see the draft plan.)
    """
    if not player_ids:
        return {}
    rows = session.execute(
        select(TeamRoster.player_id, TeamRoster.roster_slot).where(
            TeamRoster.season_year == season.year,
            TeamRoster.player_id.in_(player_ids),
        )
    ).all()
    slots: dict[int, set[str]] = {}
    for pid, slot in rows:
        if slot:
            slots.setdefault(int(pid), set()).add(slot)
    return slots


def _drafted_roster_weeks(
    session: Session, season: Season, player_ids: set[int]
) -> dict[int, dict[str, int]]:
    """Per drafted player, distinct-week counts of how they were carried that season.

    ``{"bench": n, "ir": m, "weeks": total}`` from ``team_rosters`` (week 0
    excluded; rows are week-end snapshots — see roster-snapshot-semantics). Feeds
    the opportunity-cost factor of the draft impact model: bench weeks occupy an
    active roster slot, IR / reserve weeks do not. A player never rostered after
    the draft is simply absent from the result, so opportunity degrades to
    neutral (we never fabricate a carry cost). Roster-slot history is sparse in
    early seasons, so absence here is a real "unknown", not zero.
    """
    if not player_ids:
        return {}
    rows = session.execute(
        select(TeamRoster.player_id, TeamRoster.week, TeamRoster.roster_slot).where(
            TeamRoster.season_year == season.year,
            TeamRoster.week > 0,
            TeamRoster.player_id.in_(player_ids),
        )
    ).all()
    bench: dict[int, set[int]] = {}
    ir: dict[int, set[int]] = {}
    weeks: dict[int, set[int]] = {}
    for pid, week, slot in rows:
        p, wk = int(pid), int(week)
        weeks.setdefault(p, set()).add(wk)
        if slot in BENCH_SLOTS:
            bench.setdefault(p, set()).add(wk)
        elif slot in IR_SLOTS:
            ir.setdefault(p, set()).add(wk)
    return {
        p: {"bench": len(bench.get(p, set())), "ir": len(ir.get(p, set())), "weeks": len(wk)}
        for p, wk in weeks.items()
    }


def _pick_impact(
    *,
    value: float | None,
    overall: int,
    total_picks: int,
    reg_weeks: int,
    carry: dict[str, int] | None,
    position_mean: float = 0.0,
    position_stddev: float = 1.0,
    weighted_eligible: bool = True,
) -> dict[str, Any]:
    """Composite draft impact for one pick (pure).

    ``impact = normalized_value * cost_weight * opportunity_weight``:

    * ``cost_weight`` is the draft-capital curve — an early bust and a late steal
      weigh near ``1.0``; the opposite ends decay toward :data:`COST_FLOOR`.
    * ``opportunity_weight`` amplifies *busts* by how expensively they were
      carried — a full season on the active bench costs more than one on IR. It
      is ``1.0`` for steals (a producing pick never wasted its slot) and ``1.0``
      when roster history is missing, so impact omits the carry factor rather
      than inventing a cost.

    ``impact`` is also ``None`` for positions outside QB/RB/WR/TE. The component
    breakdown travels with the pick so the UI can explain both the number and
    weighted-position eligibility.
    """
    if value is None:
        return {"impact": None, "impact_components": None}

    if not weighted_eligible or position_stddev <= 0:
        return {
            "impact": None,
            "impact_components": {
                "base_value": round(value, 2),
                "normalized_value": None,
                "position_mean": round(position_mean, 4),
                "position_stddev": round(position_stddev, 4),
                "weighted_eligible": False,
                "weighted_reason": "position_not_weighted",
                "cost_weight": 1.0,
                "opportunity_weight": 1.0,
                "bench_weeks": carry["bench"] if carry else 0,
                "ir_weeks": carry["ir"] if carry else 0,
                "opportunity_available": carry is not None,
            },
        }

    normalized_value = (value - position_mean) / position_stddev
    if abs(normalized_value) < 0.00005:
        normalized_value = 0.0
    is_steal = normalized_value > 0
    cost_weight = positional_weight(
        overall, total_picks, floor=COST_FLOOR, curve=COST_CURVE, invert=is_steal
    )

    bench_weeks = carry["bench"] if carry else 0
    ir_weeks = carry["ir"] if carry else 0
    opportunity_available = carry is not None
    if normalized_value < 0 and opportunity_available and reg_weeks > 0:
        bench_frac = min(bench_weeks / reg_weeks, 1.0)
        ir_frac = min(ir_weeks / reg_weeks, 1.0)
        opportunity_weight = 1.0 + OPP_BENCH_WEIGHT * bench_frac + OPP_IR_WEIGHT * ir_frac
    else:
        opportunity_weight = 1.0

    impact = weighted_impact(
        normalized_value,
        cost_weight=cost_weight,
        opportunity_weight=opportunity_weight,
    )
    rounded_impact = round(impact, 2)
    if rounded_impact == 0:
        rounded_impact = 0.0
    return {
        "impact": rounded_impact,
        "impact_components": {
            "base_value": round(value, 2),
            "normalized_value": round(normalized_value, 4),
            "position_mean": round(position_mean, 4),
            "position_stddev": round(position_stddev, 4),
            "weighted_eligible": True,
            "weighted_reason": None,
            "cost_weight": round(cost_weight, 4),
            "opportunity_weight": round(opportunity_weight, 4),
            "bench_weeks": bench_weeks,
            "ir_weeks": ir_weeks,
            "opportunity_available": opportunity_available,
        },
    }


def _impact_weights() -> dict[str, float]:
    """The tunable impact weights, echoed in the payload for transparency."""
    return {
        "cost_floor": COST_FLOOR,
        "cost_curve": COST_CURVE,
        "opp_bench_weight": OPP_BENCH_WEIGHT,
        "opp_ir_weight": OPP_IR_WEIGHT,
    }


def _did_not_play_detail(roster_slots: set[str]) -> str:
    """Phrase the note for a drafted player who recorded no stats all season."""
    base = (
        "Drafted but recorded no game stats all season — a season-long injury or "
        "ineligibility, not missing data."
    )
    if roster_slots & IR_SLOTS:
        return f"{base} Held in a reserve / IR slot."
    if roster_slots & BENCH_SLOTS:
        return f"{base} Carried on the active bench."
    return base


def _classify_pick_scoring(
    *,
    player: Player,
    scored_points: float | None,
    season_is_scored: bool,
    played: bool,
    roster_slots: set[str],
) -> dict[str, Any]:
    """Resolve a pick's score fields (``season_points`` + availability + note).

    A scored total passes straight through as available. Otherwise we explain
    the absence rather than invent a 0 — except a genuine season-long non-play,
    which is a real ``0.0`` the board should show with a ``zero_reason`` note.
    """
    if scored_points is not None:
        return {
            "season_points": round(scored_points, 2),
            "available": True,
            "reason": None,
            "zero_reason": None,
            "zero_detail": None,
        }

    if not season_is_scored:
        reason = "season_unscored"  # whole season has no scoring yet
    elif player.position == "DEF":
        reason = "team_defense_not_scored"  # a defense can't have a season-long 0
    elif played:
        reason = "player_unscored"  # has raw stats but no scored row
    elif not (player.gsis_id or "").strip():
        reason = "player_identity_unresolved"  # never matched to a canonical player
    else:
        # Real, fully-identified player; scored season; zero game stats all year:
        # drafted and never played (season-long injury / IR). A genuine 0.
        return {
            "season_points": 0.0,
            "available": True,
            "reason": None,
            "zero_reason": "did_not_play_season",
            "zero_detail": _did_not_play_detail(roster_slots),
        }
    return {
        "season_points": None,
        "available": False,
        "reason": reason,
        "zero_reason": None,
        "zero_detail": None,
    }


def _season_picks(session: Session, season: Season) -> list[dict[str, Any]] | None:
    """Ordered draft picks for one season, or ``None`` when none were captured.

    Each pick carries its overall number, round/slot, team + owner context, the
    drafted player, and the player's regular-season scoring resolved by
    :func:`_classify_pick_scoring` (a real total, a genuine ``0.0`` with a note,
    or ``None`` with an availability ``reason``).
    """
    owners = owner_name_map(session)
    rows = list(
        session.execute(
            select(Transaction, Player, Team)
            .join(Player, Player.player_id == Transaction.player_id)
            .join(Team, Team.team_id == Transaction.team_id)
            .where(
                Transaction.season_id == season.season_id,
                Transaction.transaction_type == "draft",
            )
            .order_by(Transaction.executed_at, Transaction.transaction_id)
        ).all()
    )
    if not rows:
        return None

    drafted_ids = {player.player_id for _, player, _ in rows}
    points = _season_points(session, season, drafted_ids)
    season_is_scored = bool(
        session.execute(
            select(PlayerStatsScored.scored_id)
            .where(PlayerStatsScored.season_id == season.season_id)
            .limit(1)
        ).scalar_one_or_none()
    )
    played = _players_with_raw(session, season, drafted_ids)
    roster_slots = _drafted_roster_slots(session, season, drafted_ids)
    roster_weeks = _drafted_roster_weeks(session, season, drafted_ids)
    reg_weeks = regular_season_weeks(session, season)
    num_teams = len({team.team_id for _, _, team in rows}) or 1

    picks: list[dict[str, Any]] = []
    for i, (_tx, player, team) in enumerate(rows):
        overall = i + 1
        scoring = _classify_pick_scoring(
            player=player,
            scored_points=points.get(player.player_id),
            season_is_scored=season_is_scored,
            played=player.player_id in played,
            roster_slots=roster_slots.get(player.player_id, set()),
        )
        picks.append(
            {
                "overall": overall,
                "round": (overall - 1) // num_teams + 1,
                "pick_in_round": (overall - 1) % num_teams + 1,
                "team_id": team.team_id,
                "team_name": period_team_name(team, season.year),
                "owner_id": team.owner_id,
                "owner_name": owners.get(team.owner_id),
                "player_id": player.player_id,
                "player_name": player.name_full,
                "position": player.position,
                "season_year": season.year,
                "num_teams": num_teams,
                # Transient inputs for the impact composite; popped in _with_values.
                "_reg_weeks": reg_weeks,
                "_carry": roster_weeks.get(player.player_id),
                **scoring,
            }
        )
    return picks


def _expected_by_slot(history: list[tuple[int, float]]) -> dict[int, float]:
    """Expected points per overall slot from a ``(overall, points)`` history pool.

    The expectation at slot *o* is the mean of every historical pick whose
    overall number lies within :data:`VALUE_SLOT_WINDOW` of *o*. Slots with no
    neighbouring data are simply absent from the result (their value is then
    unavailable, not zero).
    """
    if not history:
        return {}
    slots = {o for o, _ in history}
    expected: dict[int, float] = {}
    for o in slots:
        near = [pts for p, pts in history if abs(p - o) <= VALUE_SLOT_WINDOW]
        if near:
            expected[o] = sum(near) / len(near)
    return expected


def _clean_rounded(value: float, digits: int = 2) -> float:
    """Round a metric without leaking Python's confusing negative zero."""
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def _value_history(session: Session) -> list[tuple[int, float]]:
    """Every captured pick across all seasons as ``(overall, season_points)``.

    Only picks whose player has a scored season total contribute — unscored
    picks can't anchor an expectation.
    """
    history: list[tuple[int, float]] = []
    for season in session.execute(select(Season)).scalars().all():
        picks = _season_picks(session, season)
        if picks is None:
            continue
        for pick in picks:
            if pick["season_points"] is not None:
                history.append((pick["overall"], pick["season_points"]))
    return history


def _position_value_stats(
    session: Session, expected: dict[int, float]
) -> dict[str, tuple[float, float]]:
    """Historical raw-value mean/stddev for each weighted offensive position."""
    values: dict[str, list[float]] = defaultdict(list)
    for season in session.execute(select(Season)).scalars().all():
        picks = _season_picks(session, season)
        if picks is None:
            continue
        for pick in picks:
            points = pick["season_points"]
            exp = expected.get(pick["overall"])
            position = pick["position"]
            if points is None or exp is None or position not in WEIGHTED_POSITIONS:
                continue
            values[position].append(points - exp)
    return {
        position: (fmean(samples), pstdev(samples))
        for position, samples in values.items()
        if len(samples) >= 2 and pstdev(samples) > 0
    }


def _with_values(
    picks: list[dict[str, Any]],
    expected: dict[int, float],
    position_stats: dict[str, tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Annotate picks with ``value`` and the composite ``impact`` in place-safe copies.

    Score-state (``season_points`` / ``available`` / ``reason`` / ``zero_*``) is
    already set by :func:`_classify_pick_scoring`; this layers on ``value`` and
    then the composite ``impact`` (see :func:`_pick_impact`). A pick with no score
    keeps its gap reason. A scored pick (a real total *or* a genuine ``0.0``) gets
    ``value = season_points - expected`` when its slot has a historical anchor,
    otherwise ``insufficient_history`` for value only — its ``zero_reason`` note is
    preserved either way. ``impact`` is ``None`` when value is unavailable or
    the position is excluded from the weighted leaderboard.
    """
    total_picks = len(picks)
    out: list[dict[str, Any]] = []
    for pick in picks:
        p = dict(pick)
        p.pop("num_teams", None)
        reg_weeks = p.pop("_reg_weeks", 0)
        carry = p.pop("_carry", None)
        season_points = p["season_points"]
        if season_points is None:
            # Unavailable with a reason already set by _classify_pick_scoring.
            p["value"] = None
        else:
            exp = expected.get(p["overall"])
            if exp is None:
                p["value"] = None
                p["available"] = False
                p["reason"] = "insufficient_history"
            else:
                p["value"] = _clean_rounded(season_points - exp)
        position = str(p["position"]) if p.get("position") is not None else None
        position_mean, position_stddev = (
            (position_stats or {}).get(position, (0.0, 1.0)) if position is not None else (0.0, 1.0)
        )
        weighted_eligible = position in WEIGHTED_POSITIONS
        p.update(
            _pick_impact(
                value=p["value"],
                overall=p["overall"],
                total_picks=total_picks,
                reg_weeks=reg_weeks,
                carry=carry,
                position_mean=position_mean,
                position_stddev=position_stddev,
                weighted_eligible=weighted_eligible,
            )
        )
        out.append(p)
    return out


def draft_board(session: Session, season_id: int) -> dict[str, Any] | None:
    """Round-by-round draft board for a season, or ``None`` if no such season.

    Returns an ``available: false`` payload (never an invented grid) when the
    season has no captured draft transactions.
    """
    require_league(session)  # 503 when the pipeline has never run
    season = get_season(session, season_id)
    if season is None:
        return None

    picks = _season_picks(session, season)
    if picks is None:
        return {
            "season_id": season_id,
            "season_year": season.year,
            "available": False,
            "reason": "draft_not_captured",
            "num_teams": None,
            "rounds": [],
        }

    num_teams = picks[0]["num_teams"]
    expected = _expected_by_slot(_value_history(session))
    valued = _with_values(picks, expected, _position_value_stats(session, expected))
    rounds: dict[int, list[dict[str, Any]]] = {}
    for pick in valued:
        rounds.setdefault(pick["round"], []).append(pick)
    return {
        "season_id": season_id,
        "season_year": season.year,
        "available": True,
        "reason": None,
        "num_teams": num_teams,
        "rounds": [{"round": r, "picks": rounds[r]} for r in sorted(rounds)],
    }


def draft_value(session: Session, season_id: int) -> dict[str, Any] | None:
    """Pick-value analysis for a season (steals/busts), or ``None`` if no season."""
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None

    picks = _season_picks(session, season)
    if picks is None:
        return {
            "season_id": season_id,
            "season_year": season.year,
            "available": False,
            "reason": "draft_not_captured",
            "definition": VALUE_DEFINITION,
            "slot_window": VALUE_SLOT_WINDOW,
            "impact_definition": IMPACT_DEFINITION,
            "weights": _impact_weights(),
            "picks": [],
            "steals": [],
            "busts": [],
            "points_steals": [],
            "points_busts": [],
            "leaderboard_limit": LEADERBOARD_LIMIT,
        }

    expected = _expected_by_slot(_value_history(session))
    valued = _with_values(picks, expected, _position_value_stats(session, expected))
    scored = [p for p in valued if p["value"] is not None]
    # The full list stays sorted by the honest per-slot value (highest first);
    # Steals/busts are ranked by position-normalized composite impact.
    scored.sort(key=lambda p: p["value"], reverse=True)
    unscored = [p for p in valued if p["value"] is None]
    steals = sorted(
        [p for p in scored if p["impact"] is not None and p["impact"] > 0],
        key=lambda p: p["impact"],
        reverse=True,
    )[:LEADERBOARD_LIMIT]
    busts = sorted(
        [p for p in scored if p["impact"] is not None and p["impact"] < 0],
        key=lambda p: p["impact"],
    )[:LEADERBOARD_LIMIT]
    points_steals = sorted(
        [p for p in scored if p["value"] > 0],
        key=lambda p: p["value"],
        reverse=True,
    )[:LEADERBOARD_LIMIT]
    points_busts = sorted(
        [p for p in scored if p["value"] < 0],
        key=lambda p: p["value"],
    )[:LEADERBOARD_LIMIT]
    return {
        "season_id": season_id,
        "season_year": season.year,
        "available": True,
        "reason": None,
        "definition": VALUE_DEFINITION,
        "slot_window": VALUE_SLOT_WINDOW,
        "impact_definition": IMPACT_DEFINITION,
        "weights": _impact_weights(),
        "picks": scored + unscored,
        "steals": steals,
        "busts": busts,
        "points_steals": points_steals,
        "points_busts": points_busts,
        "leaderboard_limit": LEADERBOARD_LIMIT,
    }


def best_worst_picks(session: Session, limit: int = 5) -> dict[str, Any]:
    """Best/worst draft picks ever, across every captured season (records book)."""
    expected = _expected_by_slot(_value_history(session))
    all_valued: list[dict[str, Any]] = []
    for season in session.execute(select(Season).order_by(Season.year)).scalars().all():
        picks = _season_picks(session, season)
        if picks is None:
            continue
        all_valued.extend(p for p in _with_values(picks, expected) if p["value"] is not None)

    if not all_valued:
        return {
            "available": False,
            "reason": "draft_not_captured",
            "definition": VALUE_DEFINITION,
            "best_picks": [],
            "worst_picks": [],
        }

    by_value = sorted(all_valued, key=lambda p: p["value"], reverse=True)
    return {
        "available": True,
        "reason": None,
        "definition": VALUE_DEFINITION,
        "best_picks": by_value[:limit],
        "worst_picks": sorted(all_valued, key=lambda p: p["value"])[:limit],
    }
