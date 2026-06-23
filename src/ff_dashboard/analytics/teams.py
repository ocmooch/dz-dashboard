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
  that week (team scores can exist even when player scoring is absent, so this
  is not gated).
* :func:`team_transactions` — the season's recorded transaction log involving this team.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, TeamRoster, Transaction
from ff_pipeline.repository.queries import (
    get_player,
    get_season,
    get_team,
    injury_reports_for_week,
    matchups_for_team,
    player_season_teams,
    roster_for_team_week,
    transactions_for_team,
)
from sqlalchemy import func, select

from ff_dashboard.analytics.common import owner_name_map, require_league
from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.injuries import injury_fields
from ff_dashboard.analytics.matchups import (
    DEF_SLOTS,
    _authoritative_points,
    _identity_cluster_members,
    _injury_for_player_cluster,
    _scored_points,
    classify_zero,
    roster_sort_key,
)
from ff_dashboard.analytics.roster_snapshots import (
    is_reconstructed_week,
    reconstructed_note,
    snapshot_kind,
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
        "team_name": period_team_name(team, season.year),
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


def _expected_roster_size(session: Session, team_id: int) -> int:
    """The team-season's usual roster size — its most common week-end row count.

    Roster snapshots record the *week-end* roster, so a week where players were
    dropped and not replaced carries fewer rows. We pad such weeks up to this
    size with empty slots (rather than letting them vanish). Derived from the
    snapshots themselves, not league settings (which drift over time); ties
    resolve to the larger count so a partly-empty week never sets the bar low.
    Week 0 (the draft snapshot) is excluded — it isn't a played week.
    """
    counts = (
        session.execute(
            select(func.count())
            .select_from(TeamRoster)
            .where(TeamRoster.team_id == team_id, TeamRoster.week > 0)
            .group_by(TeamRoster.week)
        )
        .scalars()
        .all()
    )
    if not counts:
        return 0
    freq = Counter(int(c) for c in counts)
    top = max(freq.values())
    return max(c for c, f in freq.items() if f == top)


def team_roster(session: Session, team_id: int, week: int | None) -> dict[str, Any] | None:
    """The team's roster for a week (latest when ``week`` is ``None``).

    Per-player league points are included where the player was scored that week;
    they are ``null`` (never 0) for unscored slots/seasons.
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
    pairs = sorted(pairs, key=lambda rp: roster_sort_key(rp[0].roster_slot, rp[1].position))
    effective_week = week
    if effective_week is None:
        effective_week = (
            pairs[0][0].week if pairs else (weeks_available[-1] if weeks_available else 0)
        )

    is_scored = season.year in set(seasons_scored(session))
    # When the displayed week's whole roster is a reconstructed audit snapshot,
    # the per-player attribution/slots are approximate — surface one caveat so the
    # team page reads the audit week the same way the box score does (shared rule).
    roster_reconstructed = is_reconstructed_week(snapshot_kind(r) for r, _ in pairs)
    player_ids = [r.player_id for r, _ in pairs]
    cluster_members = _identity_cluster_members(session, player_ids)
    # Season-correct NFL team (e.g. a 2015 Raider reads "OAK"), falling back to
    # the current snapshot on players.nfl_team when no per-week team is stored —
    # mirrors period_team_name()'s fallback for fantasy names.
    season_teams = player_season_teams(session, player_ids, season.year)
    scored = _scored_points(
        session,
        season.season_id,
        effective_week,
        player_ids,
        cluster_members,
    )

    # Week-scoped injury designations — the same normalized field set the box
    # score surfaces, so a player reads identically on both views for that week.
    injuries = injury_reports_for_week(session, season.year, effective_week)

    players = []
    for roster_row, player in pairs:
        # Prefer NFL.com's authoritative per-player points; fall back to the
        # nflverse reconstruction only when the field is absent. Keeps the team
        # page in agreement with the box score (which does the same).
        points = _authoritative_points(roster_row)
        scored_row = scored.get(player.player_id)
        nflverse_points = scored_row[0] if scored_row is not None else None
        if points is None and scored_row is not None:
            points = nflverse_points
        if is_scored and points is None and roster_row.roster_slot not in DEF_SLOTS:
            # Same weekly-player rule as the box score: in a scored season, a
            # non-DST roster row with neither an NFL.com score nor an nflverse
            # stat line is an absence/DNP, not a scoring-data gap.
            points = 0.0
        league_points = round(points, 2) if points is not None else None
        opponent = (roster_row.extra_data or {}).get("opponent")
        zero_reason, zero_detail = classify_zero(
            league_points,
            opponent if isinstance(opponent, str) else None,
            nflverse_points,
        )
        players.append(
            {
                "player_id": player.player_id,
                "player_name": player.name_full,
                "position": player.position,
                "nfl_team": season_teams.get(player.player_id) or player.nfl_team,
                "roster_slot": roster_row.roster_slot,
                "is_starter": bool(roster_row.is_starter),
                "is_empty": False,
                "league_points": league_points,
                "zero_reason": zero_reason,
                "zero_detail": zero_detail,
                "acquisition_type": roster_row.acquisition_type,
                "acquisition_week": roster_row.acquisition_week,
                **injury_fields(
                    _injury_for_player_cluster(injuries, player.player_id, cluster_members)
                ),
            }
        )

    # Pad a short week's roster up to the team's usual size with dashed, empty
    # slots so a week where players were dropped (e.g. a pre-championship purge)
    # reads as open spots rather than a smaller roster. Negative ids keep the
    # frontend's per-row keys unique; every other field is null.
    if players:
        expected = _expected_roster_size(session, team_id)
        for i in range(max(0, expected - len(players))):
            players.append(
                {
                    "player_id": -(i + 1),
                    "player_name": None,
                    "position": None,
                    "nfl_team": None,
                    "roster_slot": None,
                    "is_starter": False,
                    "league_points": None,
                    "zero_reason": None,
                    "zero_detail": None,
                    "acquisition_type": None,
                    "acquisition_week": None,
                    "is_empty": True,
                    **injury_fields(None),
                }
            )

    return {
        "team_id": team_id,
        "season_year": season.year,
        "week": effective_week,
        "weeks_available": weeks_available,
        "is_scored": is_scored,
        "roster_reconstructed": roster_reconstructed,
        "roster_reconstructed_note": (
            reconstructed_note(effective_week) if roster_reconstructed else None
        ),
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
                "opponent_team_name": period_team_name(opp, season.year)
                if opp is not None
                else None,
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

    Team scores are authoritative from Phase 1 for every season that carries
    matchup totals, so this view is not gated on ``is_scored``.
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


# Acquisition transactions — what changed the roster's makeup. Start/sit
# (`lineup_change`, ~25k rows DB-wide) and league `setting_change` are not
# acquisitions and would bury the feed, so the team-transactions view drops them.
ACQUISITION_TXN_TYPES = frozenset({"free_agent_add", "waiver_add", "drop", "trade", "draft"})


def team_transactions(session: Session, team_id: int) -> dict[str, Any] | None:
    """The season's roster-acquisition transactions involving this team.

    Scoped to adds / drops / trades / draft (the moves that changed the roster);
    lineup changes and league setting changes are excluded — see
    :data:`ACQUISITION_TXN_TYPES`.
    """
    require_league(session)
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover
        return None

    items: list[dict[str, Any]] = []
    for t in transactions_for_team(session, team_id):
        if t.transaction_type not in ACQUISITION_TXN_TYPES:
            continue
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
                "waiver_priority_used": t.waiver_priority_used,
                "faab_bid": _faab_bid(t.extra_data),
                "counterpart_team_id": t.counterpart_team_id,
                "counterpart_team_name": period_team_name(counterpart, season.year)
                if counterpart is not None
                else None,
                "notes": t.notes,
                "extra_data": t.extra_data,
            }
        )

    return {"team_id": team_id, "season_year": season.year, "transactions": items}


def _faab_bid(extra_data: dict[str, Any] | None) -> float | None:
    """Return a FAAB bid when Phase 1 records one (2021+ ``waiver_add`` legs).

    A bid of ``0`` is a *real* outcome (a free waiver claim), distinct from a
    missing bid — so we check key *presence* rather than truthiness; an ``or``
    chain would wrongly collapse ``0`` to ``None``. Falls back to ``faab`` /
    ``bid`` only if the canonical ``faab_bid`` key is absent.
    """
    if not extra_data:
        return None
    for key in ("faab_bid", "faab", "bid"):
        if key not in extra_data:
            continue
        raw = extra_data[key]
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


# --- FAAB remaining-budget -------------------------------------------------
# The league's FAAB season budget. The 2021 switch event set it to $100 and it
# has held since; it is the base every team starts each FAAB season with.
_FAAB_BASE_BUDGET = 100.0

# A per-team mid-season budget adjustment, e.g.
#   "Dan changed Ice Station Zebra Waiver Budget from '39' to '76'"
# These setting_change rows carry team_id=NULL, so the only link to the affected
# team is its name in the description. The league-wide default
# ("changed Waiver Budget to '100'") has no from/to pair and is *not* matched.
_BUDGET_ADJUST_RE = re.compile(
    r"changed (?P<team>.+?) Waiver Budget from '(?P<before>\d+(?:\.\d+)?)' "
    r"to '(?P<after>\d+(?:\.\d+)?)'"
)


def _norm_name(value: str) -> str:
    """Whitespace-collapsed, case-folded name for matching budget-event teams."""
    return " ".join(value.split()).casefold()


def _credit_note(credit: float) -> str:
    """Human note for a mid-season budget adjustment, e.g. ``"Budget adjusted +$37"``."""
    sign = "+" if credit > 0 else "-"
    return f"Budget adjusted {sign}${abs(credit):g}"


def _faab_budget_weeks(
    spend_by_week: dict[int, float],
    credits_by_week: dict[int, float],
    base: float,
) -> tuple[list[dict[str, Any]], float, float]:
    """Derive the per-week budget timeline from weekly spend + mid-season credits.

    ``remaining(week) = (base + credits applied through week) - spend through
    week``. Only weeks with FAAB activity (a claim or an adjustment) emit a row;
    the running balance carries across the gaps. Returns ``(weeks, total_spent,
    final_remaining)``.
    """
    active = sorted(w for w in (set(spend_by_week) | set(credits_by_week)) if w >= 1)
    weeks: list[dict[str, Any]] = []
    cum_spent = 0.0
    cum_credit = 0.0
    for w in active:
        spent = round(spend_by_week.get(w, 0.0), 2)
        credit = round(credits_by_week.get(w, 0.0), 2)
        cum_spent = round(cum_spent + spent, 2)
        cum_credit = round(cum_credit + credit, 2)
        budget = round(base + cum_credit, 2)
        remaining = round(budget - cum_spent, 2)
        weeks.append(
            {
                "week": w,
                "spent": spent,
                "cumulative_spent": cum_spent,
                "budget": budget,
                "remaining": remaining,
                "adjustment": credit if credit else None,
                "note": _credit_note(credit) if credit else None,
            }
        )
    total_spent = round(cum_spent, 2)
    final_remaining = round(base + cum_credit - cum_spent, 2)
    return weeks, total_spent, final_remaining


def _budget_credits_for_team(
    session: Session, season_id: int, team_name: str | None
) -> dict[int, float]:
    """Mid-season FAAB budget credits attributed to ``team_name`` for the season.

    Each per-team budget ``setting_change`` is parsed for its name + before/after
    values; the credit is ``after - before`` applied at the event's effective
    week (preseason folds into week 1). Reproduces e.g. Ice Station Zebra's 2022
    +$37 refund. Name match is whitespace/case-insensitive against the season-
    correct team name.
    """
    credits: dict[int, float] = defaultdict(float)
    if not team_name:
        return credits
    target = _norm_name(team_name)
    rows = (
        session.execute(
            select(Transaction)
            .where(Transaction.season_id == season_id)
            .where(Transaction.transaction_type == "setting_change")
        )
        .scalars()
        .all()
    )
    for txn in rows:
        extra = txn.extra_data
        desc = extra.get("description") if isinstance(extra, dict) else None
        if not desc:
            continue
        m = _BUDGET_ADJUST_RE.search(desc)
        if m is None or _norm_name(m.group("team")) != target:
            continue
        delta = float(m.group("after")) - float(m.group("before"))
        week = txn.effective_week if txn.effective_week and txn.effective_week >= 1 else 1
        credits[week] += delta
    return credits


def team_faab_budget(session: Session, team_id: int) -> dict[str, Any] | None:
    """Per-week FAAB budget remaining for a team, derived from tracked spend.

    NFL.com exposes no weekly remaining-budget view, so this is *derived*:
    ``remaining(week) = budget_at_week - cumulative spend through that week``,
    where spend is the captured ``faab_bid`` on the team's ``waiver_add`` legs
    and ``budget_at_week`` is the $100 base plus any mid-season per-team budget
    adjustments applied at their week. FAAB-era is **data-driven** on the
    presence of captured bids in the season — pre-FAAB (waiver-priority) seasons
    return ``is_faab_era=False`` (not applicable, not a :class:`DataGap`).
    """
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover
        return None

    faab_present = (
        session.execute(
            select(Transaction.transaction_id)
            .where(Transaction.season_id == season.season_id)
            .where(func.json_extract(Transaction.extra_data, "$.faab_bid").is_not(None))
            .limit(1)
        ).first()
        is not None
    )
    if not faab_present:
        return {
            "team_id": team_id,
            "season_year": season.year,
            "is_faab_era": False,
            "available": False,
            "season_budget": None,
            "total_spent": None,
            "final_remaining": None,
            "weeks": [],
        }

    spend_by_week: dict[int, float] = defaultdict(float)
    for txn in transactions_for_team(session, team_id):
        if txn.transaction_type != "waiver_add" or txn.team_id != team_id:
            continue
        bid = _faab_bid(txn.extra_data)
        if bid is None:
            continue
        week = txn.effective_week if txn.effective_week and txn.effective_week >= 1 else 1
        spend_by_week[week] += bid

    credits_by_week = _budget_credits_for_team(
        session, season.season_id, period_team_name(team, season.year)
    )
    weeks, total_spent, final_remaining = _faab_budget_weeks(
        spend_by_week, credits_by_week, _FAAB_BASE_BUDGET
    )
    return {
        "team_id": team_id,
        "season_year": season.year,
        "is_faab_era": True,
        "available": True,
        "season_budget": _FAAB_BASE_BUDGET,
        "total_spent": total_spent,
        "final_remaining": final_remaining,
        "weeks": weeks,
    }
