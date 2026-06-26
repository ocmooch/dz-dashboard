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
from ff_pipeline.repository.queries import get_season, player_season_teams
from sqlalchemy import distinct, func, select

from ff_dashboard.analytics.adp import (
    ADP_DEFINITION,
    ADP_SOURCE_WEIGHTS,
    market_axis,
    season_adp_map,
)
from ff_dashboard.analytics.common import (
    owner_name_map,
    owner_qualified_map,
    regular_season_weeks,
    require_league,
)
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.matchups import BENCH_SLOTS, IR_SLOTS, _identity_cluster_members
from ff_dashboard.analytics.scoring import authoritative_week_points
from ff_dashboard.analytics.weighting import positional_weight, weighted_impact

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ff_dashboard.cache import AnalyticsCache

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

# The fantasy league's position universe. Every drafted pick is presented as one
# of these; the position filter and the weighted-impact model both key off this
# set. (The UI labels DEF as "DST".)
FANTASY_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")

# Raw NFL roster positions fold onto that universe. Most are 1:1; a few NFL
# positions have no fantasy slot of their own but a single clear fantasy home (a
# fullback plays RB, a placekicker is K, a team defense is DEF). A two-way player
# whose *listed* NFL position is defensive — e.g. Travis Hunter, listed CB but
# drafted and scored entirely as a receiver — folds to the offensive position he
# actually plays in this league. This is the one place that knows NFL→fantasy
# position; extend the table when a new case appears rather than special-casing a
# player by name downstream. A position with no fantasy home maps to ``None`` so
# the pick is shown honestly (no invented position) and stays out of the filter
# and the impact model.
_NFL_TO_FANTASY: dict[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "HB": "RB",
    "WR": "WR",
    "CB": "WR",  # two-way WR/CB (Travis Hunter); folds to his offensive role
    "TE": "TE",
    "K": "K",
    "PK": "K",
    "DEF": "DEF",
    "DST": "DEF",
    "D/ST": "DEF",
}


def fantasy_position(raw: str | None) -> str | None:
    """Fold a raw NFL position onto the fantasy-league universe (or ``None``).

    Returns ``None`` for a position with no fantasy home so the pick is presented
    honestly rather than mislabeled — which also keeps it out of the position
    filter and the position-normalized impact model. See ``_NFL_TO_FANTASY``.
    """
    if raw is None:
        return None
    return _NFL_TO_FANTASY.get(raw.strip().upper())


IMPACT_DEFINITION = (
    "Draft impact = position-normalized pick value scaled by how the pick was spent "
    "and carried. QB, RB, WR, and TE are compared with their own position before "
    "ranking together. An "
    "early-round bust (or a late-round steal) weighs more than the same value late "
    "(or early); and a bust carried all year on the active bench costs more than "
    "one stashed on IR / reserve. Opportunity cost amplifies weighted busts only. "
    "Positive impact = weighted steal; negative impact = weighted bust."
)


def _season_points(
    session: Session,
    season: Season,
    player_ids: set[int],
    cluster_members: dict[int, list[int]] | None = None,
) -> dict[int, float]:
    """Drafted ``player_id -> regular-season points``, resolving identity clusters.

    A draft transaction owns the canonical/roster-side id, while scored rows can
    still live on a linked source member. For each week prefer the drafted id's
    row and otherwise take the first linked member row. This prevents both gaps
    (Mike Williams 2019) and double counting when both sides are populated.

    ``cluster_members`` may be supplied by the caller (``_season_picks`` resolves
    it once and shares it with :func:`_players_with_raw`) to avoid recomputing the
    identity resolution per consumer.
    """
    if not player_ids:
        return {}
    reg = regular_season_weeks(session, season)
    if cluster_members is None:
        cluster_members = _identity_cluster_members(session, sorted(player_ids))
    lookup_ids = sorted({member for members in cluster_members.values() for member in members})
    # Score each week as coalesce(nfl_com_points, total_points) so pick value is
    # measured against the same bonus-inclusive points the box score and records
    # book show (the reconstruction omits NFL.com bonuses). At most one roster row
    # per (player, season_year, week), so the LEFT JOIN stays exact. See
    # analytics/scoring.py and docs/plans/bonus-scoring-fidelity.md.
    points = authoritative_week_points()
    rows = session.execute(
        select(
            PlayerStatsScored.player_id,
            PlayerStatsScored.week,
            func.sum(points),
        )
        .outerjoin(
            TeamRoster,
            (TeamRoster.player_id == PlayerStatsScored.player_id)
            & (TeamRoster.week == PlayerStatsScored.week)
            & (TeamRoster.season_year == season.year),
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


def _players_with_raw(
    session: Session,
    season: Season,
    player_ids: set[int],
    cluster_members: dict[int, list[int]] | None = None,
    *,
    max_week: int | None = None,
) -> set[int]:
    """``player_id`` of everyone with at least one raw stat row that season.

    Presence of a raw line means the player suited up at least once; its absence
    across a *scored* season is what separates a genuine season-long non-play
    (a real 0) from a player who simply hasn't been scored yet.

    ``max_week`` bounds the window so callers can ask the question two ways: the
    whole season (``None`` — did they *ever* suit up) or only the fantasy regular
    season (``max_week=reg`` — did they suit up while it could earn the
    regular-season points the draft value is measured on). A player who returned
    from injury only in time for the fantasy playoffs (e.g. Foreman 2018 / Brown
    2024, NFL wks 16+) is present for the first and absent for the second, which
    is what keeps them off the spurious ``player_unscored`` gap.

    ``cluster_members`` may be supplied to reuse a single identity resolution (see
    :func:`_season_points`).
    """
    if not player_ids:
        return set()
    if cluster_members is None:
        cluster_members = _identity_cluster_members(session, sorted(player_ids))
    lookup_ids = sorted({member for members in cluster_members.values() for member in members})
    conditions = [
        PlayerStatsRaw.season_year == season.year,
        PlayerStatsRaw.player_id.in_(lookup_ids),
    ]
    if max_week is not None:
        conditions.append(PlayerStatsRaw.week <= max_week)
    rows = (
        session.execute(select(distinct(PlayerStatsRaw.player_id)).where(*conditions))
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


def _has_external_identity(player: Player) -> bool:
    """Whether a drafted player is matched to *any* canonical source identity.

    Identity resolution is not gsis-only. nflverse's ``gsis_id`` is the link the
    scoring pipeline keys on, but a player can be a fully real, NFL.com-identified
    person who simply generated no nflverse weekly data to link against — e.g.
    Torry Holt, drafted in 2010 after he had already retired (NFL.com id 2501229,
    no gsis). Treating such a pick as ``player_identity_unresolved`` hides a real
    "drafted but never played" zero behind a phantom data gap. Any source id
    (gsis *or* NFL.com) counts as resolved.
    """
    return bool((player.gsis_id or "").strip() or (player.nfl_com_player_id or "").strip())


def _did_not_play_detail(roster_slots: set[str], *, played_postseason: bool = False) -> str:
    """Phrase the note for a drafted player who earned no regular-season stats.

    ``played_postseason`` distinguishes the two genuine-zero stories: a player who
    never suited up at all (season-long injury / ineligibility) from one who
    returned only after the fantasy regular season ended (Foreman 2018, Brown
    2024) — production that counts nothing toward the regular-season draft value.
    """
    if played_postseason:
        base = (
            "Drafted but recorded no game stats during the fantasy regular season — "
            "any production came only after it ended, so it counts nothing toward the "
            "regular-season pick value."
        )
    else:
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
    played_regular: bool,
    played_season: bool,
    roster_slots: set[str],
) -> dict[str, Any]:
    """Resolve a pick's score fields (``season_points`` + availability + note).

    A scored total passes straight through as available. Otherwise we explain
    the absence rather than invent a 0 — except a genuine non-play, which is a
    real ``0.0`` the board should show with a ``zero_reason`` note.

    The two "played" signals are deliberately scoped differently. Pick value is
    measured over the fantasy *regular* season, so ``player_unscored`` (a true
    scoring-pipeline gap — raw lines exist but were never scored) keys on
    ``played_regular``. ``played_season`` (raw lines anywhere, incl. the fantasy
    playoffs) only refines the genuine-zero note, so a player who returned just in
    time for the playoffs reads as a real regular-season zero rather than a gap.
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
    elif played_regular:
        reason = "player_unscored"  # has regular-season raw stats but no scored row
    elif not _has_external_identity(player):
        reason = "player_identity_unresolved"  # never matched to a canonical player
    else:
        # Real, fully-identified player; scored season; no regular-season game
        # stats: drafted and contributed nothing to the regular season (season-long
        # injury / IR, or a return that came only once the playoffs began). A
        # genuine 0 the board shows with a note.
        return {
            "season_points": 0.0,
            "available": True,
            "reason": None,
            "zero_reason": "did_not_play_season",
            "zero_detail": _did_not_play_detail(roster_slots, played_postseason=played_season),
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
    # Resolve identity clusters once and share across the points + raw-stat reads
    # (each previously re-ran the per-player identity N+1 over the same ids).
    cluster_members = _identity_cluster_members(session, sorted(drafted_ids))
    points = _season_points(session, season, drafted_ids, cluster_members)
    season_is_scored = bool(
        session.execute(
            select(PlayerStatsScored.scored_id)
            .where(PlayerStatsScored.season_id == season.season_id)
            .limit(1)
        ).scalar_one_or_none()
    )
    reg_weeks = regular_season_weeks(session, season)
    # Two windows: "played at all this season" (note phrasing) vs "played during
    # the fantasy regular season" (the only window pick value is measured on, so
    # the one that gates the player_unscored scoring-gap). See _classify_pick_scoring.
    played_season = _players_with_raw(session, season, drafted_ids, cluster_members)
    played_regular = _players_with_raw(
        session, season, drafted_ids, cluster_members, max_week=reg_weeks
    )
    roster_slots = _drafted_roster_slots(session, season, drafted_ids)
    roster_weeks = _drafted_roster_weeks(session, season, drafted_ids)
    # Season-correct NFL team (e.g. a 2015 Raider reads "OAK"), falling back to
    # the current snapshot on players.nfl_team when no per-week team is stored —
    # mirrors the box score / team page rule (see player_season_teams).
    season_teams = player_season_teams(session, sorted(drafted_ids), season.year)
    num_teams = len({team.team_id for _, _, team in rows}) or 1

    picks: list[dict[str, Any]] = []
    for i, (_tx, player, team) in enumerate(rows):
        overall = i + 1
        scoring = _classify_pick_scoring(
            player=player,
            scored_points=points.get(player.player_id),
            season_is_scored=season_is_scored,
            played_regular=player.player_id in played_regular,
            played_season=player.player_id in played_season,
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
                "position": fantasy_position(player.position),
                "nfl_team": season_teams.get(player.player_id) or player.nfl_team,
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


def _season_picks_cached(
    session: Session, season: Season, cache: AnalyticsCache | None = None
) -> list[dict[str, Any]] | None:
    """:func:`_season_picks` memoized per season for the current pipeline run.

    A season's picks are stable between Phase 1 runs, so the same board feeds
    every consumer (its own endpoint, the all-seasons history sweep, the records
    book) without recomputation. Without a cache it falls back to a direct call
    (the unit tests drive the analytics layer with no app cache)."""
    if cache is None:
        return _season_picks(session, season)
    return cache.get_or_compute(
        session, f"draft_season_picks:{season.season_id}", lambda: _season_picks(session, season)
    )


def _build_history_model(session: Session, cache: AnalyticsCache | None) -> dict[str, Any]:
    """Single all-seasons sweep → ``{"expected", "position_stats"}``.

    Both league-wide anchors (the per-slot expectation and the per-position
    value mean/stddev that standardizes impact) derive from one pass over every
    captured draft. Previously ``_value_history`` and ``_position_value_stats``
    each swept all seasons independently — two full passes, each re-running every
    season's picks — so a single endpoint hit recomputed the whole draft history
    twice. Here the per-season picks are gathered once (and cached) and the
    position pass runs in memory off that gather."""
    history: list[tuple[int, float]] = []
    gathered: list[list[dict[str, Any]]] = []
    for season in session.execute(select(Season)).scalars().all():
        picks = _season_picks_cached(session, season, cache)
        if picks is None:
            continue
        gathered.append(picks)
        history.extend(
            (pick["overall"], pick["season_points"])
            for pick in picks
            if pick["season_points"] is not None
        )
    expected = _expected_by_slot(history)
    values: dict[str, list[float]] = defaultdict(list)
    for picks in gathered:
        for pick in picks:
            points = pick["season_points"]
            exp = expected.get(pick["overall"])
            position = pick["position"]
            if points is None or exp is None or position not in WEIGHTED_POSITIONS:
                continue
            values[position].append(points - exp)
    position_stats = {
        position: (fmean(samples), pstdev(samples))
        for position, samples in values.items()
        if len(samples) >= 2 and pstdev(samples) > 0
    }
    return {"expected": expected, "position_stats": position_stats}


def _draft_history_model(session: Session, cache: AnalyticsCache | None = None) -> dict[str, Any]:
    """The cached league-wide draft anchors (``expected`` + ``position_stats``).

    Keyed only on the pipeline run, so it is computed once and shared by every
    season's board/value response and the records book — not recomputed per
    request as the prior two-sweep design did."""
    if cache is None:
        return _build_history_model(session, cache)
    return cache.get_or_compute(
        session, "draft_history_model", lambda: _build_history_model(session, cache)
    )


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


def _attach_adp(
    picks: list[dict[str, Any]], adp_map: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Layer the market (reach/value) axis onto valued picks, in safe copies.

    The ADP fields are kept **orthogonal** to the scoring fields: ``adp_available``
    is its own sub-state, so a pick can have a score but no ADP (a deep sleeper)
    or an ADP but no score (a drafted-but-never-played bust). When the season
    captured no ADP at all the reason is ``adp_not_captured``; a single missing
    player in an otherwise-covered season is ``no_market_data`` (outside the
    consensus top ~200 — kickers, most DSTs, rookies, retirees).
    """
    captured = bool(adp_map)
    out: list[dict[str, Any]] = []
    for pick in picks:
        p = dict(pick)
        blend = adp_map.get(p["player_id"])
        if blend is None:
            p.update(
                {
                    "adp": None,
                    "adp_sources": [],
                    "adp_source_spread": None,
                    "adp_format": None,
                    "adp_format_fallback": False,
                    "adp_delta": None,
                    "market_label": None,
                    "adp_available": False,
                    "adp_reason": "no_market_data" if captured else "adp_not_captured",
                }
            )
        else:
            p.update(blend)
            p.update(market_axis(blend["adp"], p["overall"]))
            p["adp_available"] = True
            p["adp_reason"] = None
        out.append(p)
    return out


def draft_board(
    session: Session, season_id: int, cache: AnalyticsCache | None = None
) -> dict[str, Any] | None:
    """Round-by-round draft board for a season, or ``None`` if no such season.

    Returns an ``available: false`` payload (never an invented grid) when the
    season has no captured draft transactions.
    """
    require_league(session)  # 503 when the pipeline has never run
    season = get_season(session, season_id)
    if season is None:
        return None

    picks = _season_picks_cached(session, season, cache)
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
    model = _draft_history_model(session, cache)
    valued = _with_values(picks, model["expected"], model["position_stats"])
    valued = _attach_adp(valued, season_adp_map(session, season_id, cache))
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


def draft_value(
    session: Session, season_id: int, cache: AnalyticsCache | None = None
) -> dict[str, Any] | None:
    """Pick-value analysis for a season (steals/busts), or ``None`` if no season."""
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None

    picks = _season_picks_cached(session, season, cache)
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
            "adp_definition": ADP_DEFINITION,
            "adp_weights": ADP_SOURCE_WEIGHTS,
            "reaches": [],
            "values": [],
            "leaderboard_limit": LEADERBOARD_LIMIT,
        }

    model = _draft_history_model(session, cache)
    valued = _with_values(picks, model["expected"], model["position_stats"])
    valued = _attach_adp(valued, season_adp_map(session, season_id, cache))
    # Market axis (independent of scoring): reaches drafted earlier than the
    # consensus (most-negative delta first), values later (most-positive first).
    adp_scored = [p for p in valued if p["adp_delta"] is not None]
    reaches = sorted([p for p in adp_scored if p["adp_delta"] < 0], key=lambda p: p["adp_delta"])[
        :LEADERBOARD_LIMIT
    ]
    values = sorted(
        [p for p in adp_scored if p["adp_delta"] > 0],
        key=lambda p: p["adp_delta"],
        reverse=True,
    )[:LEADERBOARD_LIMIT]
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
        "adp_definition": ADP_DEFINITION,
        "adp_weights": ADP_SOURCE_WEIGHTS,
        "reaches": reaches,
        "values": values,
        "leaderboard_limit": LEADERBOARD_LIMIT,
    }


def best_worst_picks(
    session: Session, limit: int = 5, cache: AnalyticsCache | None = None
) -> dict[str, Any]:
    """Best/worst draft picks ever, across every captured season (records book)."""
    expected = _draft_history_model(session, cache)["expected"]
    all_valued: list[dict[str, Any]] = []
    for season in session.execute(select(Season).order_by(Season.year)).scalars().all():
        picks = _season_picks_cached(session, season, cache)
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


# Minimum ADP-covered picks before a manager's market tendency is reported, so a
# handful of picks can't masquerade as a "tendency". The honest denominator
# (``n_picks_with_adp``) always travels in the payload either way.
TENDENCY_MIN_PICKS = 8

TENDENCY_DEFINITION = (
    "Draft tendencies aggregate the market (reach/value) axis across every "
    "captured draft for a manager. Reach rate is the share of their ADP-covered "
    "picks taken earlier than consensus; mean delta is the average gap between "
    "actual slot and ADP (positive = tends to wait/find value, negative = tends "
    "to reach); discipline is the average distance from consensus (lower = sticks "
    "closer to the board). Only picks with a blended ADP count."
)


def draft_tendencies(session: Session, cache: AnalyticsCache | None = None) -> dict[str, Any]:
    """Per-manager market (reach/value) tendencies across all captured drafts."""
    require_league(session)
    owners = owner_name_map(session)
    qualified = owner_qualified_map(session)

    deltas: dict[int, list[float]] = defaultdict(list)
    reaches: dict[int, int] = defaultdict(int)
    values: dict[int, int] = defaultdict(int)
    by_position: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    recent_team: dict[int, tuple[int, str | None]] = {}

    for season in session.execute(select(Season).order_by(Season.year)).scalars().all():
        picks = _season_picks_cached(session, season, cache)
        if picks is None:
            continue
        enriched = _attach_adp(picks, season_adp_map(session, season.season_id, cache))
        for p in enriched:
            owner_id = p.get("owner_id")
            if owner_id is None or p["adp_delta"] is None:
                continue
            deltas[owner_id].append(p["adp_delta"])
            if p["market_label"] == "reach":
                reaches[owner_id] += 1
            elif p["market_label"] == "value":
                values[owner_id] += 1
            position = p.get("position")
            if position is not None:
                by_position[owner_id][position].append(p["adp_delta"])
            year = p.get("season_year") or season.year
            if owner_id not in recent_team or year >= recent_team[owner_id][0]:
                recent_team[owner_id] = (year, p.get("team_name"))

    managers: list[dict[str, Any]] = []
    for owner_id, owner_deltas in deltas.items():
        n = len(owner_deltas)
        managers.append(
            {
                "owner_id": owner_id,
                "owner_name": owners.get(owner_id),
                "team_name": recent_team.get(owner_id, (0, None))[1],
                "qualified": bool(qualified.get(owner_id, True)),
                "n_picks_with_adp": n,
                "mean_delta": _clean_rounded(fmean(owner_deltas), 1),
                "reach_rate": _clean_rounded(reaches[owner_id] / n, 3),
                "value_rate": _clean_rounded(values[owner_id] / n, 3),
                "discipline": _clean_rounded(fmean([abs(d) for d in owner_deltas]), 1),
                "by_position": [
                    {
                        "position": pos,
                        "n": len(pos_deltas),
                        "mean_delta": _clean_rounded(fmean(pos_deltas), 1),
                    }
                    for pos, pos_deltas in sorted(by_position[owner_id].items())
                ],
                "sufficient": n >= TENDENCY_MIN_PICKS,
            }
        )

    # Qualified managers first, then by sample size — never hide anyone.
    managers.sort(key=lambda m: (m["qualified"], m["n_picks_with_adp"]), reverse=True)
    return {
        "available": bool(managers),
        "reason": None if managers else "draft_not_captured",
        "definition": TENDENCY_DEFINITION,
        "min_picks": TENDENCY_MIN_PICKS,
        "weights": ADP_SOURCE_WEIGHTS,
        "managers": managers,
    }
