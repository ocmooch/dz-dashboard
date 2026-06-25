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

from ff_pipeline.repository.models import (
    Matchup,
    PlayerIdentityLink,
    PlayerStatsScored,
    Transaction,
)
from ff_pipeline.repository.models import Projection as ProjectionModel
from ff_pipeline.repository.models import ScoringRule as ScoringRuleModel
from ff_pipeline.repository.queries import (
    get_matchup,
    get_season,
    get_team,
    injury_reports_for_week,
    player_season_positions,
    roster_for_team_week,
)
from ff_pipeline.scoring.engine import apply_rules
from ff_pipeline.scoring.rules import ScoringRule as ScoringRuleDataclass
from ff_pipeline.scoring.rules import ScoringRules
from sqlalchemy import select

from ff_dashboard.analytics.bracket import postseason_classification
from ff_dashboard.analytics.common import owner_name_map, require_league
from ff_dashboard.analytics.coverage import coverage_status_for_projection_week, seasons_scored
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.injuries import InjuryFields, injury_fields
from ff_dashboard.analytics.matchup_flags import (
    flags_for_game,
    season_score_context,
    week_score_context,
)
from ff_dashboard.analytics.player_status import should_suppress_status
from ff_dashboard.analytics.roster_snapshots import (
    is_reconstructed_week,
    reconstructed_note,
    snapshot_kind,
)
from ff_dashboard.analytics.season_schedule import season_schedule

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

# A roster slot that names exactly one NFL position. When the league starts a
# player here the slot *is* the league's position call (eligibility is enforced
# upstream), so the displayed badge follows it for fantasy-special players whose
# nflverse position differs (a TE-slotted Taysom Hill reads TE). Flex slots
# (W/R, R/W/T, …) and bench/IR name no single position and are absent here, so
# those rows fall back to the season-correct position.
_CONCRETE_SLOT_POSITION: dict[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "DEF": "DEF",
    "DST": "DEF",
    "D/ST": "DEF",
}


def _slot_to_position(slot: str | None) -> str | None:
    """The position a concrete single-position slot names, else ``None``."""
    if slot is None:
        return None
    return _CONCRETE_SLOT_POSITION.get(slot)


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


def _extra_str(roster_row: Any, key: str) -> str | None:
    extra = roster_row.extra_data or {}
    value = extra.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


# The 2022 NFL Week-17 Bills@Bengals game was suspended after Damar Hamlin's
# cardiac arrest and ruled a no-contest. Upstream (danger-zone) resolves it as a
# per-player substitute `wk17_partial + wk19` (Week 18 skipped) and stamps each
# affected wk17 roster slot with a ``hamlin_substitute`` provenance block. The
# dashboard is display-only: it reads that flag, renders the corrected score with
# the two-component breakdown, and suppresses the (now false) zero-classification
# paths. All affordances key off the *presence* of the flag — never a hardcoded
# matchup id or year.
HAMLIN_CONTEXT_LABEL = "Wk17+19"
HAMLIN_CONTEXT_DETAIL = (
    "Game cancelled (Hamlin no-contest); the league counted this player's Week-17 "
    "stats from before play stopped plus their Week-19 (Wild Card) game — Week 18 was skipped."
)
HAMLIN_RESOLUTION_NOTE = (
    "The 2022 NFL Week-17 Bills@Bengals game was suspended after Damar Hamlin's "
    "cardiac arrest and ruled a no-contest by the NFL (never replayed). For each "
    "affected player the league counted their Week-17 stats accrued before play "
    "stopped plus their Week-19 (Wild Card) game; Week 18 was skipped. These "
    "substitute scores are reconstructed from public data — the Week-17 box score "
    "plus the Week-19 stat lines — and a recovered private league note corroborated "
    "only the Week-19 component and was incomplete."
)


def _hamlin_substitute(roster_row: Any) -> dict[str, Any] | None:
    """The ``hamlin_substitute`` provenance block for a roster row, if present.

    Set upstream on every affected 2022-wk17 slot; its presence is the sole
    trigger for every Hamlin no-contest affordance in the box score.
    """
    extra = roster_row.extra_data or {}
    value = extra.get("hamlin_substitute")
    return value if isinstance(value, dict) else None


def _hamlin_component(block: Any) -> dict[str, Any] | None:
    """One ``{points, raw_stats}`` component (wk17_partial or wk19) for the UI."""
    if not isinstance(block, dict):
        return None
    points = block.get("points")
    raw_stats = block.get("raw_stats")
    return {
        "points": float(points)
        if isinstance(points, (int, float)) and not isinstance(points, bool)
        else None,
        "raw_stats": raw_stats if isinstance(raw_stats, dict) else {},
    }


def _hamlin_player_context(hamlin: dict[str, Any] | None) -> dict[str, Any] | None:
    """Shape the per-player no-contest substitution split for the box score.

    Exposes the Week-17 partial and the Week-19 (Wild Card) add-on separately so
    the UI can show the cancelled-game partial and the add-on as distinct rows.
    """
    if hamlin is None:
        return None
    league_points = hamlin.get("league_points")
    return {
        "basis": hamlin.get("basis"),
        "league_points": float(league_points)
        if isinstance(league_points, (int, float)) and not isinstance(league_points, bool)
        else None,
        "wk17_partial": _hamlin_component(hamlin.get("wk17_partial")),
        "wk19": _hamlin_component(hamlin.get("wk19")),
    }


def _reserve_eligibility_status(
    roster_row: Any, injury: Any, injury_payload: InjuryFields, *, player_played: bool
) -> str | None:
    slot = (roster_row.roster_slot or "").upper()
    if slot not in IR_SLOTS:
        return None
    # A reserve-slot player who actually played cannot truthfully carry a
    # did-not-play roster status (NFL.com current-state drift); drop the
    # anachronistic IR/IA/SUS and fall through to injury-report / slot context.
    roster_status_label = _extra_str(roster_row, "player_status_label")
    roster_status = _extra_str(roster_row, "player_status")
    if should_suppress_status(roster_status_label, played=player_played):
        roster_status_label = None
    if should_suppress_status(roster_status, played=player_played):
        roster_status = None
    return (
        roster_status_label
        or roster_status
        or injury_payload.get("injury_status")
        or injury_payload.get("injury_practice_status")
        or (injury.practice_status if injury is not None else None)
        or roster_row.roster_slot
    )


def _roster_data_context(
    session: Session,
    *,
    season_id: int,
    team_id: int,
    player_id: int,
    week: int,
) -> tuple[str, str] | None:
    txns = list(
        session.execute(
            select(Transaction).where(
                Transaction.season_id == season_id,
                Transaction.player_id == player_id,
            )
        )
        .scalars()
        .all()
    )
    return _roster_data_context_from_transactions(
        txns,
        team_id=team_id,
        week=week,
    )


def _roster_data_context_from_transactions(
    txns: list[Any],
    *,
    team_id: int,
    week: int,
) -> tuple[str, str] | None:
    # An acquisition is any inbound move onto this team. ``draft`` rows carry
    # ``direction == "add"`` (effective_week 0), every other inbound type carries
    # ``direction == "in"``; accept both. Excluding ``add`` here is the bug that
    # made drafted-then-re-acquired players look like late additions: a player
    # drafted in W0, dropped, and re-added via waiver/FA in W11 has a real W1
    # roster row but no *in*-direction add until W11, so ``week < first_add``
    # fired a false "Roster drift" badge. Counting the draft (W0) clears it.
    team_add_weeks = [
        int(t.effective_week)
        for t in txns
        if t.team_id == team_id
        and t.direction in {"in", "add"}
        and t.effective_week is not None
        and t.transaction_type in {"add", "draft", "free_agent_add", "waiver_add", "trade"}
    ]
    if team_add_weeks:
        first_add = min(team_add_weeks)
        if week < first_add:
            return (
                "DATA",
                f"Roster drift: snapshot shows this player on this team in W{week}, "
                f"but transactions first add him in W{first_add}. Points/status are shown; "
                "roster context is suspect.",
            )

    # NOTE: we deliberately do *not* flag a snapshot roster_slot that disagrees
    # with that week's ``lineup_change`` ``to_slot`` values. Moving a player
    # between starting slots and the bench (BN) is routine, allowed lineup
    # management for any ownable player — he never entered or left the team, so
    # it is not a data-integrity problem. A DB-wide audit found 38/40 such
    # "slot conflict" firings were pure start/bench juggling (the snapshot is a
    # point-in-time capture; the player simply moved within the week). The only
    # genuinely notable slot case — a player parked in an IR/RES slot who has
    # lost the status that made him eligible there — is surfaced separately by
    # the reserve-eligibility path in ``_score_context`` (slot in ``IR_SLOTS``),
    # which gives accurate RES context instead of a misleading "roster drift".
    return None


def _score_context(
    *,
    data_context: tuple[str, str] | None,
    league_points: float | None,
    zero_reason: str | None,
    zero_detail: str | None,
    nfl_opponent: str | None,
    nfl_game_status: str | None,
    roster_slot: str | None,
    roster_status: str | None,
    roster_status_label: str | None,
    reserve_eligibility_status: str | None,
    injury_payload: InjuryFields,
    player_played: bool,
) -> tuple[str | None, str | None]:
    if data_context is not None:
        return data_context

    # NFL.com stamps a player's *current* status onto historical weeks, so a
    # player who demonstrably played can carry a did-not-play badge (IA/IR/SUS).
    # Suppress an incompatible roster status whenever there's proof the player
    # played; keep game-time injury designations (Q/D/P) and genuine DNPs.
    if should_suppress_status(roster_status, played=player_played):
        roster_status = None

    injury_status = injury_payload.get("injury_status")
    injury_body = injury_payload.get("injury_body_part")
    injury_practice = injury_payload.get("injury_practice_status")
    slot = (roster_slot or "").upper()
    matchup = " ".join(part for part in (nfl_opponent, nfl_game_status) if part)

    if zero_reason == "bye":
        return "Bye", "NFL team was on bye; zero is expected."

    if zero_reason == "unexpected":
        return "Check", zero_detail

    if zero_reason == "did_not_play":
        if injury_status == "Out":
            detail = f"Ruled out{f' - {injury_body}' if injury_body else ''}."
            return "Out", detail
        if roster_status:
            label = roster_status
            detail = roster_status_label or "Roster badge captured from NFL.com."
            return label, detail
        if slot in IR_SLOTS:
            detail = "Reserve slot; team played but no stat/scored row was recorded."
            if matchup:
                detail = f"{detail} Game: {matchup}."
            if injury_practice:
                detail = f"{detail} Injury report practice: {injury_practice}."
                return "INJ", detail
            return str(roster_slot), detail
        reason = "Team played but no stat/scored row was recorded."
        if matchup:
            reason = f"{reason} Game: {matchup}."
        if injury_practice:
            reason = f"{reason} Injury report practice: {injury_practice}."
        else:
            reason = f"{reason} No injury designation was captured."
        return "DNP", reason

    if slot in IR_SLOTS:
        if league_points is not None and league_points > 0:
            reason = (
                f"Recorded in {roster_slot} while also credited with points; "
                "those points are real but excluded from bench/optimal totals. "
                "The current data does not prove why the reserve slot and stat line coexist."
            )
            if reserve_eligibility_status:
                reason = f"{reason} Eligibility context: {reserve_eligibility_status}."
            else:
                reason = f"{reason} No reserve eligibility designation was captured."
            # A reserve-slot player who is *also* credited with points clearly
            # played and scored, so we never escalate this to an "INJ" badge:
            # an injury-report row for the same week does not prove the points
            # were earned despite an injury, and labeling a 12-point line "INJ"
            # is exactly the misleading-injury implication we want to avoid. The
            # certain fact is the reserve slot; surface that and keep any injury
            # nuance in the detail text only.
            return "RES", reason
        if reserve_eligibility_status:
            return roster_slot, f"Reserve slot context: {reserve_eligibility_status}."
        return roster_slot, "Reserve slot; no additional eligibility context captured."

    if roster_status:
        detail = roster_status_label or "Roster badge captured from NFL.com."
        return roster_status, detail

    return None, None


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


def _real_projection(*, proj_row: Any, rules: ScoringRules) -> float | None:
    """A player's *real* projected points, or ``None`` when there isn't one.

    Prefer the stored ``projected_points``; fall back to scoring the raw
    ``projected_stats``. A zero result is treated as *no projection*: the source
    (Sleeper) emits hollow all-zero rows for players it didn't project and for
    entire pre-coverage seasons, and a bare ``0.0`` next to a player reads as a
    real forecast of zero, which it isn't.
    """
    if proj_row is None:
        return None
    if proj_row.projected_points is not None and float(proj_row.projected_points) != 0.0:
        return round(float(proj_row.projected_points), 2)
    computed = _projected_points_from_stats(proj_row.projected_stats, rules)
    if computed is not None and round(computed, 2) != 0.0:
        return round(computed, 2)
    return None


def _batch_projections(
    session: Any,
    player_ids: list[int],
    season_year: int,
    week: int,
    cluster_members: dict[int, list[int]] | None = None,
) -> dict[int, ProjectionModel]:
    """Latest projection row per player for a given season/week, in one query."""
    if not player_ids:
        return {}
    from sqlalchemy import func

    cluster_members = cluster_members or {pid: [pid] for pid in player_ids}
    lookup_ids = sorted({member for members in cluster_members.values() for member in members})

    # Subquery: max fetched_at per player for this season/week.
    sub = (
        select(
            ProjectionModel.player_id,
            func.max(ProjectionModel.fetched_at).label("latest"),
        )
        .where(
            ProjectionModel.player_id.in_(lookup_ids),
            ProjectionModel.season_year == season_year,
            ProjectionModel.week == week,
        )
        .group_by(ProjectionModel.player_id)
        .subquery()
    )
    rows = (
        session.execute(
            select(ProjectionModel)
            .join(
                sub,
                (ProjectionModel.player_id == sub.c.player_id)
                & (ProjectionModel.fetched_at == sub.c.latest),
            )
            # The subquery's max(fetched_at) is scoped to this season/week, but the
            # outer row match is on (player_id, fetched_at) — so without repeating
            # the season/week filter here, a different week sharing the same
            # fetched_at would join in and overwrite the right row.
            .where(
                ProjectionModel.season_year == season_year,
                ProjectionModel.week == week,
            )
        )
        .scalars()
        .all()
    )
    by_member = {int(r.player_id): r for r in rows}
    out: dict[int, ProjectionModel] = {}
    for player_id in player_ids:
        for member_id in cluster_members[player_id]:
            row = by_member.get(member_id)
            if row is not None:
                out[player_id] = row
                break
    return out


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
    session: Session,
    season_id: int,
    week: int,
    player_ids: list[int],
    cluster_members: dict[int, list[int]] | None = None,
) -> dict[int, tuple[float, dict[str, Any]]]:
    """``player_id -> (total_points, breakdown)`` for one (season, week)."""
    if not player_ids:
        return {}
    cluster_members = cluster_members or {pid: [pid] for pid in player_ids}
    lookup_ids = sorted({member for members in cluster_members.values() for member in members})
    rows = session.execute(
        select(
            PlayerStatsScored.player_id,
            PlayerStatsScored.total_points,
            PlayerStatsScored.points_breakdown,
        ).where(
            PlayerStatsScored.season_id == season_id,
            PlayerStatsScored.week == week,
            PlayerStatsScored.player_id.in_(lookup_ids),
        )
    ).all()
    by_member = {int(pid): (float(pts), bd or {}) for pid, pts, bd in rows}
    out: dict[int, tuple[float, dict[str, Any]]] = {}
    for player_id in player_ids:
        for member_id in cluster_members[player_id]:
            row = by_member.get(member_id)
            if row is not None:
                out[player_id] = row
                break
    return out


def _identity_cluster_members(session: Session, player_ids: list[int]) -> dict[int, list[int]]:
    """Roster-player id -> member ids to read as the same canonical player.

    Resolves the whole input set in two queries instead of the per-player
    ``player_identity_cluster`` lookup (an N+1 that dominated the draft sweeps —
    every drafted player triggered three round-trips). Semantics are unchanged:
    each input id maps to its cluster's members with the input id listed first;
    an id with no link row is its own singleton cluster.
    """
    ids = sorted({int(pid) for pid in player_ids})
    if not ids:
        return {}
    # member -> canonical for the inputs (a missing row means the id is canonical).
    canonical_of = {
        int(member): int(canonical)
        for member, canonical in session.execute(
            select(
                PlayerIdentityLink.member_player_id, PlayerIdentityLink.canonical_player_id
            ).where(PlayerIdentityLink.member_player_id.in_(ids))
        ).all()
    }
    canonicals = {canonical_of.get(pid, pid) for pid in ids}
    members_by_canonical: dict[int, set[int]] = {}
    for canonical, member in session.execute(
        select(PlayerIdentityLink.canonical_player_id, PlayerIdentityLink.member_player_id).where(
            PlayerIdentityLink.canonical_player_id.in_(canonicals)
        )
    ).all():
        members_by_canonical.setdefault(int(canonical), set()).add(int(member))
    out: dict[int, list[int]] = {}
    for pid in ids:
        canonical = canonical_of.get(pid, pid)
        members = members_by_canonical.get(canonical, set()) | {canonical, pid}
        out[pid] = [pid, *sorted(member for member in members if member != pid)]
    return out


def _injury_for_player_cluster(
    injuries: dict[int, Any], player_id: int, cluster_members: dict[int, list[int]]
) -> Any | None:
    for member_id in cluster_members.get(player_id, [player_id]):
        injury = injuries.get(member_id)
        if injury is not None:
            return injury
    return None


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
    # When every known per-row snapshot is an audit reconstruction, the whole
    # week's roster is reconstructed (not a live weekly capture). In that case
    # per-player "roster drift" is systemic, not player-specific, so we suppress
    # the per-player DATA badge and surface a single team-level caveat instead.
    roster_reconstructed = is_reconstructed_week(snapshot_kind(r) for r, _ in roster)
    player_ids = [r.player_id for r, _ in roster]
    # Season-correct NFL position: ``players.position`` is a single
    # current/last-known snapshot, so it misrepresents any season before a
    # position change (a 2014 WR shown as a later-career TE). Resolve the
    # position the player actually played that season, falling back to the
    # snapshot when none is stored. Mirrors the season-correct NFL-team path.
    season_positions = player_season_positions(session, player_ids, season.year)

    def _position(player: Any) -> str | None:
        """The player's true season position — used for sort + optimal eligibility."""
        return season_positions.get(player.player_id) or player.position

    def _badge_position(slot: str | None, player: Any) -> str | None:
        """The position to *display*. When the league started the player in a
        concrete single-position slot (QB/RB/WR/TE/K/DEF), trust that designation
        — it carries the league's eligibility call for fantasy-special players
        (e.g. a TE-slotted Taysom Hill reads TE, not his nflverse QB). A flex or
        bench slot names no single position, so fall back to the season position
        (then the snapshot)."""
        return _slot_to_position(slot) or _position(player)

    cluster_members = _identity_cluster_members(session, player_ids)
    scored = _scored_points(session, season.season_id, week, player_ids, cluster_members)
    projections = _batch_projections(session, player_ids, season.year, week, cluster_members)
    projection_coverage = coverage_status_for_projection_week(session, season.year, week)
    projections_available_for_week = projection_coverage["status"] == "present"
    projection_reason = (
        str(projection_coverage["reason"])
        if projection_coverage.get("reason") is not None
        else None
    )
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
        key=lambda rp: roster_sort_key(rp[0].roster_slot, _position(rp[1])),
    ):
        slot = roster_row.roster_slot
        is_starter = (
            bool(roster_row.is_starter) and slot not in BENCH_SLOTS and slot not in IR_SLOTS
        )
        scored_row = scored.get(player.player_id)
        breakdown = scored_row[1] if scored_row is not None else {}

        # The 2022 wk17 no-contest substitution (Hamlin) carries its own
        # combined points breakdown — surface it so passing yards / receptions /
        # FGs render instead of the empty breakdown left by the voided wk17 game.
        hamlin = _hamlin_substitute(roster_row)
        if hamlin is not None:
            hamlin_breakdown = hamlin.get("points_breakdown")
            if isinstance(hamlin_breakdown, dict):
                breakdown = hamlin_breakdown

        # Prefer NFL.com's authoritative per-player points (they sum to the team
        # score and cover players nflverse never scored — a real 0.0, not a gap);
        # fall back to the nflverse reconstruction only when the field is absent.
        nflverse_points = scored_row[0] if scored_row is not None else None
        points = _authoritative_points(roster_row)
        if points is None:
            points = nflverse_points
        if points is None and slot not in DEF_SLOTS:
            # In a scored season, a non-defense roster row with neither an
            # NFL.com score nor an nflverse stat line is a player absence, not
            # a per-row scoring gap. Keep DEF strict because missing DST rows
            # are reconstruction holes.
            points = 0.0
        league_points = round(points, 2) if points is not None else None

        available = points is not None
        reason: str | None = None
        if not available:
            reason = "team_defense_not_scored" if slot in DEF_SLOTS else "no_scored_data"

        # Explain a 0.0 result: a bye / DNP status reason, a plain played-0, or a
        # flagged "unexpected" 0. Uses the per-week opponent ("Bye") + whether the
        # player has any nflverse stat line as evidence of having played.
        opponent = _extra_str(roster_row, "opponent")
        # Suppress the false zero-classification for a no-contest substitute:
        # league_points is now > 0 but nflverse has no wk17 row, so
        # classify_zero would misfire "did_not_play" / "unexpected". Branch on
        # the provenance flag before classify_zero runs.
        if hamlin is not None:
            zero_reason, zero_detail = None, None
        else:
            zero_reason, zero_detail = classify_zero(league_points, opponent, nflverse_points)

        # Projection vs actual. Use the authoritative projected_points when stored;
        # fall back to scoring projected_stats with the season's rules when the
        # pipeline loaded raw stat projections but didn't apply scoring yet. A
        # *zero* projection is not a real forecast — Sleeper returns hollow,
        # all-zero rows for unprojected players (and entire pre-2018 seasons), so
        # treat a 0 as "no projection" (renders a gap / dash) rather than a bogus
        # 0.0 next to the player.
        projection = _real_projection(
            proj_row=projections.get(player.player_id), rules=scoring_rules
        )
        projection_delta = (
            round(league_points - projection, 2)
            if league_points is not None and projection is not None
            else None
        )
        projection_available = projections_available_for_week
        player_projection_reason = None
        if projection is None and not projections_available_for_week:
            player_projection_reason = projection_reason
        team_point_share = (
            round(league_points / total_score, 4)
            if league_points is not None and total_score is not None and total_score > 0
            else None
        )

        injury = _injury_for_player_cluster(injuries, player.player_id, cluster_members)
        injury_payload = injury_fields(injury)
        roster_status = _extra_str(roster_row, "player_status")
        roster_status_label = _extra_str(roster_row, "player_status_label")
        # "Played" = has a real nflverse stat line (an organic 0 counts) or a
        # positive league score. Used to suppress NFL.com current-state-drift
        # statuses (IA/IR/SUS) on players who clearly played that week.
        player_played = nflverse_points is not None or (
            league_points is not None and league_points > 0
        )
        reserve_eligibility = _reserve_eligibility_status(
            roster_row, injury, injury_payload, player_played=player_played
        )
        # On a reconstructed (all-audit) week, skip the per-player drift check —
        # the team-level caveat covers it, and a badge on every row would bury
        # the genuinely player-specific context (DNP / Out / reserve+points).
        data_context = (
            None
            if roster_reconstructed
            else _roster_data_context(
                session,
                season_id=season.season_id,
                team_id=team_id,
                player_id=player.player_id,
                week=week,
            )
        )
        context_label: str | None
        context_detail: str | None
        if hamlin is not None:
            # The no-contest substitution context takes precedence over every
            # other badge (DNP/IR/injury) — the player's wk17 game was cancelled.
            context_label, context_detail = HAMLIN_CONTEXT_LABEL, HAMLIN_CONTEXT_DETAIL
        else:
            context_label, context_detail = _score_context(
                data_context=data_context,
                league_points=league_points,
                zero_reason=zero_reason,
                zero_detail=zero_detail,
                nfl_opponent=opponent,
                nfl_game_status=_extra_str(roster_row, "game_status"),
                roster_slot=slot,
                roster_status=roster_status,
                roster_status_label=roster_status_label,
                reserve_eligibility_status=reserve_eligibility,
                injury_payload=injury_payload,
                player_played=player_played,
            )
        entry = {
            "roster_slot": slot,
            "player_id": player.player_id,
            "player_name": player.name_full,
            "position": _badge_position(slot, player),
            "nfl_opponent": opponent,
            "nfl_game_status": _extra_str(roster_row, "game_status"),
            "roster_status": roster_status,
            "roster_status_label": roster_status_label,
            "reserve_eligibility_status": reserve_eligibility,
            "league_points": league_points,
            "is_starter": is_starter,
            "breakdown": breakdown,
            "projection": projection,
            "projection_delta": projection_delta,
            "projection_available": projection_available,
            "projection_reason": player_projection_reason,
            "team_point_share": team_point_share,
            "available": available,
            "reason": reason,
            "zero_reason": zero_reason,
            "zero_detail": zero_detail,
            "context_label": context_label,
            "context_detail": context_detail,
            "hamlin_substitute": _hamlin_player_context(hamlin),
            "lineup_value": None,
            **injury_payload,
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
            optimal_candidates.append({"position": _position(player), "points": effective})

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
        "roster_reconstructed": roster_reconstructed,
        "roster_reconstructed_note": reconstructed_note(week) if roster_reconstructed else None,
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

    # Shared postseason tier (championship / playoff / consolation) for this game.
    _pc = postseason_classification(session, m.season_id)["by_matchup_id"].get(matchup_id) or {}
    bracket_tier = _pc.get("tier")
    game_label = _pc.get("game_label")

    if season.year not in set(seasons_scored(session)):
        return {
            "matchup_id": matchup_id,
            "season_year": season.year,
            "week": m.week,
            "available": False,
            "reason": "season_unscored",
            "is_playoff": bool(m.is_playoff),
            "bracket_tier": bracket_tier,
            "game_label": game_label,
        }

    # Projection coverage is a property of the (season, week), identical for both
    # teams — surface it once at the box level so the UI can show a single
    # top-level "no projections for this season" note instead of a gap chip on
    # every player row.
    projection_coverage = coverage_status_for_projection_week(session, season.year, m.week)
    projections_available = projection_coverage["status"] == "present"
    projection_reason = (
        None if projections_available else str(projection_coverage.get("reason") or "")
    ) or None

    home = _team_box(session, m.team_id, season, m.week, m.team_score)

    away: dict[str, Any] | None = None
    winner_team_id: int | None = None
    margin: float | None = None
    if m.opponent_team_id is not None:
        away = _team_box(session, m.opponent_team_id, season, m.week, m.opponent_score)
        # Winner from the authoritative team scores (the real game result).
        if m.team_score is not None and m.opponent_score is not None:
            margin = round(abs(m.team_score - m.opponent_score), 2)
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

    # Superlative flags — the same set the weekly grid shows, so the two views
    # never disagree. Entering records (for the upset flag) come from the existing
    # regular-season helper; bye/unscored games simply produce no flags.
    entering = _entering_records(session, season, m.week)

    def flag_side(team_id: int | None, score: float | None) -> dict[str, Any] | None:
        if team_id is None:
            return None
        return {
            "team_id": team_id,
            "score": round(score, 2) if score is not None else None,
            "entering_record": entering.get(team_id, {"wins": 0, "losses": 0, "ties": 0}),
        }

    flags = flags_for_game(
        team_a=flag_side(m.team_id, m.team_score),
        team_b=flag_side(m.opponent_team_id, m.opponent_score),
        winner_team_id=winner_team_id,
        margin=margin,
        week=m.week,
        season_ctx=season_score_context(session, season.season_id, season.year),
        week_ctx=week_score_context(session, season.season_id, m.week),
        bracket_tier=bracket_tier,
    )

    # Matchup-level no-contest banner: shown on every matchup that holds an
    # affected player on either side, driven purely off the provenance flag.
    sides = [home] + ([away] if away is not None else [])
    has_substitute = any(
        entry.get("hamlin_substitute") is not None for side in sides for entry in side["lineup"]
    )
    resolution_note = HAMLIN_RESOLUTION_NOTE if has_substitute else None

    return {
        "matchup_id": matchup_id,
        "season_year": season.year,
        "week": m.week,
        "available": True,
        "is_playoff": bool(m.is_playoff),
        "bracket_tier": bracket_tier,
        "game_label": game_label,
        "projections_available": projections_available,
        "projection_reason": projection_reason,
        "resolution_note": resolution_note,
        "home": home,
        "away": away,
        "winner_team_id": winner_team_id,
        "margin": margin,
        "flags": flags,
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
    # Computed once per call and shared across every game card; the route caches
    # this whole function per (season, week).
    season_ctx = season_score_context(session, season_id, season.year)
    week_ctx = {m.team_id: m.team_score for m in rows if m.team_score is not None}
    # Shared postseason classification for this season; cheap and reused per card.
    classification = postseason_classification(session, season_id)["by_matchup_id"]

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

        team_a = team_ref(m.team_id, m.team_score, winner_team_id == m.team_id)
        team_b = team_ref(
            m.opponent_team_id, m.opponent_score, winner_team_id == m.opponent_team_id
        )
        tier_entry = classification.get(m.matchup_id) or {}
        bracket_tier = tier_entry.get("tier")
        games.append(
            {
                "matchup_id": m.matchup_id,
                "is_playoff": bool(m.is_playoff),
                "bracket_tier": bracket_tier,
                "game_label": tier_entry.get("game_label"),
                "team_a": team_a,
                "team_b": team_b,
                "margin": margin,
                "winner_team_id": winner_team_id,
                "flags": flags_for_game(
                    team_a=team_a,
                    team_b=team_b,
                    winner_team_id=winner_team_id,
                    margin=margin,
                    week=week,
                    season_ctx=season_ctx,
                    week_ctx=week_ctx,
                    bracket_tier=bracket_tier,
                ),
            }
        )

    return {
        "season_id": season_id,
        "season_year": season.year,
        "week": week,
        "is_scored": season.year in set(seasons_scored(session)),
        "games": games,
    }
