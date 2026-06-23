"""Tiered classifier for NFL.com ``setting_change`` transactions (the /seasons/ page).

Replaces the old 6-regex allowlist that silently dropped ~88% of rows. Every
``setting_change`` is mapped to a canonical type with a tier (T1/T2/T3), a human
label, an audience-facing sentence, an off/in-season phase, and — where rows form
a deliberate same-day/same-type cluster — collapsed into one elevated event.
**Nothing is dropped:** unmatched/future types degrade to T3 with their raw text,
and every routine row lands in a per-season collapsible bucket.

The per-type spec is the locked Decisions log in
``docs/archive/seasons-league-changes-inventory.md`` (#1-#31). Roster/scoring detail
is resolved from the state tables in :mod:`ff_dashboard.analytics.league_history`
(``_roster_changes`` / ``_scoring_rule_changes``); the matching headline here is
absorbed when that concrete diff is already shown for the season.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Season, Transaction
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# --- NFL Week-1 (Thursday opener) kickoff per season. Validated against the
#     267-row phase oracle in the inventory: every boundary falls between that
#     season's last off-season row and its first in-season row.
WEEK1_KICKOFF: dict[int, date] = {
    2010: date(2010, 9, 9),
    2011: date(2011, 9, 8),
    2012: date(2012, 9, 5),
    2013: date(2013, 9, 5),
    2014: date(2014, 9, 4),
    2015: date(2015, 9, 10),
    2016: date(2016, 9, 8),
    2017: date(2017, 9, 7),
    2018: date(2018, 9, 6),
    2019: date(2019, 9, 5),
    2020: date(2020, 9, 10),
    2021: date(2021, 9, 9),
    2022: date(2022, 9, 8),
    2023: date(2023, 9, 7),
    2024: date(2024, 9, 5),
    2025: date(2025, 9, 4),
}
# Future seasons not yet in the table: Sept-1 sentinel. Extend WEEK1_KICKOFF when
# a new season's real opener is known.
_KICKOFF_FALLBACK = (9, 1)


def phase_for(executed_at: datetime | date | None, filed_year: int) -> str:
    """``off_season`` if before that (FILED) season's Week-1 kickoff, else ``in_season``.

    Computed against the *filed* season year — not a re-attributed display year —
    to match the phase oracle (e.g. the 2022-01-16 Adjusted-Pts rows are ``off``
    relative to 2022 even though they display under 2021).
    """
    if executed_at is None:
        return "off_season"
    kickoff = WEEK1_KICKOFF.get(filed_year) or date(filed_year, *_KICKOFF_FALLBACK)
    day = executed_at.date() if isinstance(executed_at, datetime) else executed_at
    return "off_season" if day < kickoff else "in_season"


@dataclass(frozen=True)
class RawSettingChange:
    season_id: int
    year: int  # filed year (from the Season join)
    executed_at: datetime | None
    description: str  # extra_data.description, verbatim
    actor: str | None  # transactions.notes


# --- canonical-type detection. Ordered: most specific first. Anchored on the
#     setting name + ``from``/``to`` where a value-string could otherwise be
#     mistaken for another setting (e.g. Waiver Type's after-value is "Waiver
#     Budget"). Validated to classify all 267 real rows with zero catch-all.
_DETECTORS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), canonical)
    for pattern, canonical in (
        (r"Adjusted Pts For Week", "adjusted_points"),
        (r"League Schedule for Week", "schedule_week_edit"),
        (r"Waiver Type (from|to) '", "waiver_type"),
        (r"changed Waiver Budget (to|from) '", "waiver_budget_league"),
        (r"Waiver Budget (from|to) '", "waiver_budget_team"),
        (r"Waiver Period (from|to) '", "waiver_period"),
        (r"Waiver Priority (from|to) '", "waiver_priority"),
        (r"Player Adds Count", "player_adds_count"),
        (r"Player Trades Count", "player_trades_count"),
        (r"Edit Poll Permission", "edit_poll_permission"),
        (r"Edit Story Permission", "edit_story_permission"),
        (r"Logo Lock", "logo_lock"),
        (r"Lineup Changes Lock", "lineup_lock"),
        (r"assigned League Management Privileges", "mgmt_privileges_assigned"),
        (r"removed League Management Privileges", "mgmt_privileges_removed"),
        (r"updated scoring settings", "scoring_settings"),
        (r"updated roster positions", "roster_positions"),
        (r"updated playoff teams", "playoff_teams"),
        (r"updated the Draft Board", "draft_board"),
        (r"Playoff Settings (from|to) '", "playoff_settings"),
        (r"Trade Review Type (from|to) '", "trade_review_type"),
        (r"Trade Reject Time (from|to) '", "trade_reject_time"),
        (r"Trade Deadline (from|to) '", "trade_deadline"),
        (r"Standings Tiebreaker (from|to) '", "standings_tiebreaker"),
        (r"Post Draft Players (from|to) '", "post_draft_players"),
        (r"Undroppable List (from|to) '", "undroppable_list"),
        (r"Fee for Joining League (from|to) '", "fee"),
        (r"Time Per Pick (from|to) '", "time_per_pick"),
        (r"randomized Custom Draft Order", "draft_order_randomized"),
        (r"Draft Type (from|to) '", "draft_type"),
        (r"Draft Time (from|to) '", "draft_time"),
        (r"Draft Order (from|to) '", "draft_order"),
        (r"Reset the draft", "draft_reset"),
        (r"Division (from|to) '", "division_assignment"),
    )
)

# canonical_type -> display category (reuses the existing taxonomy where it exists)
_CATEGORY: dict[str, str] = {
    "scoring_settings": "scoring_rules",
    "adjusted_points": "scoring_rules",
    "roster_positions": "roster_slots",
    "playoff_settings": "playoffs",
    "playoff_teams": "playoffs",
    "waiver_type": "waiver",
    "waiver_budget_league": "waiver",
    "waiver_budget_team": "waiver",
    "waiver_period": "waiver",
    "waiver_priority": "waiver",
    "trade_review_type": "trades",
    "trade_reject_time": "trades",
    "trade_deadline": "trades",
    "fee": "money",
    "standings_tiebreaker": "standings",
    "post_draft_players": "transactions",
    "undroppable_list": "transactions",
    "draft_type": "draft",
    "draft_time": "draft",
    "draft_order": "draft",
    "draft_order_randomized": "draft",
    "draft_reset": "draft",
    "draft_board": "draft",
    "schedule_week_edit": "schedule",
    "division_assignment": "divisions",
    "edit_poll_permission": "admin",
    "edit_story_permission": "admin",
    "logo_lock": "admin",
    "lineup_lock": "admin",
    "player_adds_count": "admin",
    "player_trades_count": "admin",
    "mgmt_privileges_assigned": "commissioner",
    "mgmt_privileges_removed": "commissioner",
    "other": "admin",
}

_LABEL: dict[str, str] = {
    "scoring_settings": "Scoring settings",
    "adjusted_points": "Manual scoring adjustment",
    "roster_positions": "Roster positions",
    "playoff_settings": "Playoff format",
    "playoff_teams": "Playoff field",
    "waiver_type": "Waiver system",
    "waiver_budget_league": "Waiver system",
    "waiver_budget_team": "Per-team FAAB",
    "waiver_period": "Waiver period",
    "waiver_priority": "Waiver priority",
    "trade_review_type": "Trade approval",
    "trade_reject_time": "Trade reject window",
    "trade_deadline": "Trade deadline",
    "fee": "Entry fee",
    "standings_tiebreaker": "Tiebreaker",
    "post_draft_players": "Post-draft players",
    "undroppable_list": "Undroppable list",
    "draft_type": "Draft format",
    "draft_time": "Draft scheduling",
    "draft_order": "Draft order",
    "draft_order_randomized": "Draft order",
    "draft_reset": "Draft reset",
    "draft_board": "Draft board",
    "schedule_week_edit": "Weekly schedule edit",
    "division_assignment": "Division assignment",
    "edit_poll_permission": "Permission toggle",
    "edit_story_permission": "Permission toggle",
    "logo_lock": "Logo lock",
    "lineup_lock": "Lineup lock",
    "player_adds_count": "Add-count correction",
    "player_trades_count": "Trade-count correction",
    "mgmt_privileges_assigned": "Commissioner assigned",
    "mgmt_privileges_removed": "Commissioner removed",
    "other": "League setting",
}


@dataclass
class ClassifiedChange:
    raw: RawSettingChange
    canonical_type: str
    category: str
    human_label: str
    tier: str  # T1 | T2 | T3
    treatment: str  # PASS | MISSING | HEDGE | COLLAPSE | STATE | AGG | MERGE
    before: str | None
    after: str | None
    phase: str
    display_year: int
    event_group_key: str | None = None
    members: list[ClassifiedChange] = field(default_factory=list)


def _parse_values(desc: str) -> tuple[str | None, str | None]:
    both = re.search(r" from '([^']*)' to '([^']*)'", desc)
    if both:
        return both.group(1), both.group(2)
    only = re.search(r" to '([^']*)'", desc)
    if only:
        return None, only.group(1)
    return None, None


def _iso_date(executed_at: datetime | None) -> str:
    return executed_at.date().isoformat() if executed_at is not None else "unknown"


def classify(raw: RawSettingChange) -> ClassifiedChange:
    """Map one raw row to its canonical type + Decisions-log treatment.

    SPLIT types (#1/#7/#8/#18) resolve their tier here from recoverable detail;
    aggregation grouping and the final emitted dict are produced by
    :func:`setting_change_events`. Unmatched rows degrade to T3 ``other``.
    """
    canonical = "other"
    for pattern, name in _DETECTORS:
        if pattern.search(raw.description):
            canonical = name
            break

    before, after = _parse_values(raw.description)
    phase = phase_for(raw.executed_at, raw.year)
    display_year = raw.year
    category = _CATEGORY.get(canonical, "admin")
    label = _LABEL.get(canonical, "League setting")
    day = _iso_date(raw.executed_at)

    # defaults; overridden per type below
    tier = "T3"
    treatment = "COLLAPSE"
    group: str | None = None

    if canonical in {"scoring_settings", "roster_positions"}:
        # SPLIT (#1/#2): resolved against the state-table diff when present this
        # season (tier decided in setting_change_events); else hedged T3.
        tier, treatment = "T1", "STATE"
    elif canonical == "playoff_settings":  # (#3)
        tier, treatment = "T1", "PASS"
    elif canonical == "playoff_teams":  # (#4) field size not derivable -> routine
        # "Updated playoff teams" recurs almost every season with no recoverable
        # detail; it is noise, not a notable change. Fold into the routine bucket.
        tier, treatment = "T3", "COLLAPSE"
    elif canonical in {"waiver_type", "waiver_budget_league"}:  # (#5) FAAB switch
        tier, treatment, group = "T1", "MERGE", f"faab-{raw.year}"
    elif canonical == "waiver_period":  # (#6) minor waiver-window tweak -> routine
        tier, treatment = "T3", "COLLAPSE"
    elif canonical == "trade_review_type":  # (#7) SPLIT by era
        if raw.year <= 2011:
            tier, treatment = "T2", "PASS"
        else:
            tier, treatment = "T3", "COLLAPSE"  # 2023-25 annual re-confirm
    elif canonical == "trade_reject_time":  # (#9) minor window tweak -> routine
        tier, treatment = "T3", "COLLAPSE"
    elif canonical == "trade_deadline":  # (#8) SPLIT
        if (before or "").strip().lower() == "no deadline":
            tier, treatment = "T2", "PASS"  # 2019 first-ever deadline: notable, not major
        else:
            tier, treatment = "T3", "COLLAPSE"  # 2011 net-zero shuffle
    elif canonical in {"fee", "standings_tiebreaker"}:
        # #10 entry fee · #11 tiebreaker — genuine, outcome-relevant settings (T2)
        tier, treatment = "T2", "PASS"
    elif canonical in {"post_draft_players", "undroppable_list"}:
        # #12/#13 originating standards — set-and-forget defaults -> routine
        tier, treatment = "T3", "COLLAPSE"
    elif canonical in {"time_per_pick", "draft_board"}:
        # #18 draft-clock logistics · #20 ambiguous/unrecoverable -> routine bucket
        tier, treatment = "T3", "COLLAPSE"
    elif canonical == "schedule_week_edit":  # (#21) aggregate -> T2
        tier, treatment, group = "T2", "AGG", f"sched-{raw.year}-{day}"
    elif canonical == "division_assignment":  # (#22) aggregate -> T2 (notable, not major)
        tier, treatment, group = "T2", "AGG", f"div-{raw.year}-{day}"
    elif canonical in {"logo_lock", "lineup_lock"}:  # (#25) aggregate -> T2
        tier, treatment, group = "T2", "AGG", f"punish-{raw.year}"
    elif canonical == "waiver_priority":  # (#26) aggregate same-day; small=routine
        tier, treatment, group = "T2", "AGG", f"wpri-{raw.year}-{day}"
    elif canonical == "waiver_budget_team":  # (#27)
        tier, treatment = "T2", "MISSING"
    elif canonical == "adjusted_points":  # (#28) aggregate -> T1, re-attribute
        display_year = raw.year - 1  # filed in the Jan offseason; belongs to prior season
        tier, treatment, group = "T1", "AGG", f"adjpts-{display_year}"
    elif canonical in {"mgmt_privileges_assigned", "mgmt_privileges_removed"}:  # (#31)
        tier, treatment, group = "T1", "AGG", f"commish-{raw.year}"
    elif canonical == "other":  # catch-all: never drop
        tier, treatment = "T3", "HEDGE"
    # all remaining (draft_type/time/order/randomized/reset, permissions,
    # add/trade counts) keep the T3 / COLLAPSE defaults.

    return ClassifiedChange(
        raw=raw,
        canonical_type=canonical,
        category=category,
        human_label=label,
        tier=tier,
        treatment=treatment,
        before=before,
        after=after,
        phase=phase,
        display_year=display_year,
        event_group_key=group,
    )


# ---------------------------------------------------------------------------
# Audience rephrasing
# ---------------------------------------------------------------------------
def _money(value: str | None) -> str:
    if value is None:
        return "?"
    try:
        return f"${float(value):g}"
    except ValueError:
        return f"${value}"


def _missing_sentence(c: ClassifiedChange) -> str:
    actor = c.raw.actor or "A manager"
    when = _iso_date(c.raw.executed_at)
    base = {
        "playoff_teams": (
            f"{actor} finalized the playoff field on {when}. NFL.com records the "
            "action but not the field size, so the exact bracket size isn't recoverable."
        ),
        "draft_board": (
            f"{actor} updated the draft board on {when}. NFL.com records the action "
            "but not what changed."
        ),
        # waiver_budget_team is handled by _emit_budget_team (verified context).
    }
    return base.get(
        c.canonical_type,
        f"{actor} changed a league setting on {when}; specifics aren't recorded.",
    )


def _pass_sentence(c: ClassifiedChange) -> str:
    b, a = c.before, c.after
    t = c.canonical_type
    if t == "fee":
        return f"Buy-in set to {_money(a)}" + (f" (was {_money(b)})." if b else ".")
    if t == "playoff_settings":
        return f"Playoff bracket set to {a}" + (f" (was {b})." if b else ".")
    if t == "trade_review_type":
        return f"Trade approval changed to “{a}”" + (f" (was “{b}”)." if b else ".")
    if t == "trade_reject_time":
        return f"Pending-trade window changed to {a}" + (f" (was {b})." if b else ".")
    if t == "trade_deadline":
        return f"First trade deadline set: {a} (was {b})." if b else f"Trade deadline set to {a}."
    if t == "waiver_period":
        return f"Waiver claim window changed to {a}" + (f" (was {b})." if b else ".")
    if t == "standings_tiebreaker":
        return f"Standings ties now broken by {a}" + (f" (was {b})." if b else ".")
    if t == "post_draft_players":
        return f"Undrafted players treated as {a} (was {b}). In place since {c.display_year}."
    if t == "undroppable_list":
        return f"Undroppable list set to {a} (was {b}). In place since {c.display_year}."
    if t == "time_per_pick":
        return f"Draft pick clock set to {a}s" + (f" (was {b}s)." if b else ".")
    return f"Changed to {a}" + (f" (was {b})." if b else ".")


_SOURCE = "nfl_com_transaction_log"


def _detail(
    c: ClassifiedChange,
    *,
    title: str,
    summary: str,
    tier: str,
    certainty: str = "source_limited",
    missing_context: bool = False,
    members: list[dict[str, Any]] | None = None,
    before: str | None = None,
    after: str | None = None,
) -> dict[str, Any]:
    return {
        "category": c.category,
        "title": title,
        "summary": summary,
        "before": before,
        "after": after,
        "source": _SOURCE,
        "certainty": certainty,
        "changed_at": c.raw.executed_at.isoformat() if c.raw.executed_at is not None else None,
        "participants_joined": None,
        "participants_left": None,
        "description_gap": missing_context,
        "tier": tier,
        "human_label": title,
        "phase": c.phase,
        "event_group_key": c.event_group_key,
        "missing_context": missing_context,
        "members": members or [],
        "canonical_type": c.canonical_type,
    }


def _member_detail(c: ClassifiedChange) -> dict[str, Any]:
    """A T3 sub-row: verbatim description, retained so a collapse can expand to it."""
    return _detail(
        c,
        title=c.human_label,
        summary=c.raw.description,
        tier="T3",
        certainty="source_limited",
        before=c.before,
        after=c.after,
    )


# ---------------------------------------------------------------------------
# Aggregation + emit
# ---------------------------------------------------------------------------
# Verified context for specific per-team FAAB budget events. NFL.com records the
# budget change but not its reason; where the reason has been confirmed from the
# transaction log it is stated here as fact (keyed by (year, team)). Absent an
# entry, the event keeps the honest "reason not recorded" hedge.
_BUDGET_EVENT_CONTEXT: dict[tuple[int, str], str] = {
    (2022, "Ice Station Zebra"): (
        "The $37 increase is a refund of a reversed waiver claim: the team won "
        "Dameon Pierce for $37, the claim was undone about 12 hours later, and the "
        "budget was restored — so its effective season spend stays at the $100 cap."
    ),
}


def _emit_budget_team(c: ClassifiedChange) -> dict[str, Any]:
    """Per-team FAAB budget change — name the team, and state the refund reason
    when it has been verified from the transaction log (otherwise hedge)."""
    target = _budget_target(c.raw.description)
    actor = c.raw.actor or "A manager"
    title = f"{target} — FAAB budget" if target else c.human_label
    base = f"{actor} adjusted {target or 'a team'}'s FAAB budget mid-season ({c.before}→{c.after})."
    context = _BUDGET_EVENT_CONTEXT.get((c.raw.year, target)) if target else None
    if context:
        return _detail(
            c,
            title=title,
            summary=f"{base} {context}",
            tier=c.tier,
            certainty="verified",
            missing_context=False,
            before=c.before,
            after=c.after,
        )
    return _detail(
        c,
        title=title,
        summary=f"{base} The reason isn't recorded — likely a correction.",
        tier=c.tier,
        certainty="source_limited",
        missing_context=True,
        before=c.before,
        after=c.after,
    )


def _emit_individual(c: ClassifiedChange) -> dict[str, Any]:
    if c.canonical_type == "waiver_budget_team":
        return _emit_budget_team(c)
    if c.treatment == "MISSING":
        return _detail(
            c,
            title=c.human_label,
            summary=_missing_sentence(c),
            tier=c.tier,
            certainty="source_limited",
            missing_context=True,
            before=c.before,
            after=c.after,
        )
    # PASS
    return _detail(
        c,
        title=c.human_label,
        summary=_pass_sentence(c),
        tier=c.tier,
        certainty="verified",
        before=c.before,
        after=c.after,
    )


def _emit_group(
    _key: str, items: list[ClassifiedChange]
) -> tuple[dict[str, Any] | None, list[ClassifiedChange]]:
    """Collapse a same-key cluster into ONE elevated event.

    Returns (event, leftovers). ``leftovers`` are rows that should fall through to
    the per-season routine bucket instead of forming an elevated event (e.g. a
    trivially small waiver-priority swap).
    """
    head = items[0]
    members = [_member_detail(i) for i in items]
    actor = head.raw.actor or "The commissioner"
    n = len(items)

    if head.canonical_type in {"waiver_type", "waiver_budget_league"}:  # MERGE -> FAAB
        budget = next((i.after for i in items if i.canonical_type == "waiver_budget_league"), None)
        was = next((i.before for i in items if i.canonical_type == "waiver_type"), None)
        summary = "Switched to FAAB waivers" + (f" ({_money(budget)} budget)." if budget else ".")
        if was:
            summary += f" Previously {was}."
        return (
            _detail(
                head,
                title="Waiver system",
                summary=summary,
                tier="T1",
                certainty="verified",
                members=members,
            ),
            [],
        )
    if head.canonical_type == "division_assignment":
        summary = f"Division realignment — {n} team{'s' if n != 1 else ''} reassigned."
        return (
            _detail(
                head,
                title="Division realignment",
                summary=summary,
                tier="T2",
                certainty="verified",
                members=members,
            ),
            [],
        )
    if head.canonical_type == "schedule_week_edit":
        summary = f"Rebuilt the regular-season schedule ({n} weekly edits)."
        return (
            _detail(
                head,
                title="Schedule rebuild",
                summary=summary,
                tier="T2",
                certainty="source_limited",
                missing_context=True,
                members=members,
            ),
            [],
        )
    if head.canonical_type in {"logo_lock", "lineup_lock"}:
        summary = (
            f"{actor} locked a team's logo and lineup-change ability mid-season "
            "after an offensive team name aimed at the commissioner."
        )
        return (
            _detail(
                head,
                title="Commissioner penalty",
                summary=summary,
                tier="T2",
                certainty="source_limited",
                members=members,
            ),
            [],
        )
    if head.canonical_type == "waiver_priority":
        if n < 3:  # trivial correction (2017 two-team swap) -> routine bucket
            return (None, items)
        summary = (
            f"{actor} manually reordered waiver priority for {n} teams; the reason isn't recorded."
        )
        return (
            _detail(
                head,
                title="Waiver priority reorder",
                summary=summary,
                tier="T2",
                certainty="source_limited",
                members=members,
            ),
            [],
        )
    if head.canonical_type == "adjusted_points":
        summary = (
            f"{actor} corrected Week 17 scores for {n} teams (each from 0) after a scoring glitch."
        )
        return (
            _detail(
                head,
                title="Manual scoring adjustment",
                summary=summary,
                tier="T1",
                certainty="verified",
                members=members,
            ),
            [],
        )
    if head.canonical_type in {"mgmt_privileges_assigned", "mgmt_privileges_removed"}:
        return _emit_commish(head, items, members)

    # unknown group -> routine
    return (None, items)


def _privilege_target(desc: str) -> str | None:
    m = re.search(r"Privileges (?:to|from) ([^.]+)\.?", desc)
    return m.group(1).strip() if m else None


def _budget_target(desc: str) -> str | None:
    """The team named in a per-team FAAB budget change.

    Per-team budget events carry no ``team_id`` (they are league-level rows keyed
    only to a season); the only link to the affected team is its name embedded in
    the verbatim description, e.g. ``"Dan changed Ice Station Zebra Waiver Budget
    from '39' to '76'"`` -> ``"Ice Station Zebra"``. The league-wide default
    (``"changed Waiver Budget to '100'"``) has no team and yields ``None``.
    """
    m = re.search(r"changed (.+?) Waiver Budget", desc)
    return m.group(1).strip() if m else None


def _emit_commish(
    head: ClassifiedChange, items: list[ClassifiedChange], members: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[ClassifiedChange]]:
    """Commissioner handoff (#31): filter co-manager noise (assigned-then-removed
    same person same year), elevate the net succession signal to T1, and cross-
    reference the canonical commissioner history rather than duplicating it."""
    assigned = {
        _privilege_target(i.raw.description)
        for i in items
        if i.canonical_type == "mgmt_privileges_assigned"
    }
    removed = {
        _privilege_target(i.raw.description)
        for i in items
        if i.canonical_type == "mgmt_privileges_removed"
    }
    net_assigned = sorted(n for n in assigned - removed if n)
    net_removed = sorted(n for n in removed - assigned if n)
    if not net_assigned and not net_removed:
        return (None, items)  # pure co-manager churn -> routine bucket
    bits = []
    if net_assigned:
        bits.append("granted to " + ", ".join(net_assigned))
    if net_removed:
        bits.append("removed from " + ", ".join(net_removed))
    summary = "League-manager privileges " + "; ".join(bits) + ". See the Commissioner history."
    return (
        _detail(
            head,
            title="Commissioner change",
            summary=summary,
            tier="T1",
            certainty="source_limited",
            members=members,
        ),
        [],
    )


def _load_raw(session: Session) -> list[RawSettingChange]:
    rows = session.execute(
        select(Season.year, Transaction.extra_data, Transaction.executed_at, Transaction.notes)
        .join(Transaction, Transaction.season_id == Season.season_id)
        .where(Transaction.transaction_type == "setting_change")
        .order_by(Season.year, Transaction.transaction_id)
    ).all()
    out: list[RawSettingChange] = []
    for year, extra, executed_at, notes in rows:
        raw = extra or {}
        description = raw.get("description") if isinstance(raw, Mapping) else None
        if not description:
            continue
        out.append(
            RawSettingChange(
                season_id=0,
                year=int(year),
                executed_at=executed_at,
                description=str(description),
                actor=str(notes).strip() if notes else None,
            )
        )
    return out


def setting_change_events(
    session: Session, *, resolved_cats_by_year: dict[int, set[str]] | None = None
) -> dict[int, list[dict[str, Any]]]:
    """Per display-year list of emitted change/event dicts (extended detail shape).

    ``resolved_cats_by_year`` maps a year to the set of categories that already
    carry a concrete state-table diff this season (roster/scoring). A STATE
    headline whose category is resolved is *absorbed* (that diff is the real
    explanation); otherwise it degrades to a hedged T3 note. Nothing else is
    dropped: every other row is an individual event, a member of an aggregated
    event, or a member of the per-season routine bucket.
    """
    resolved = resolved_cats_by_year or {}
    classified = [classify(r) for r in _load_raw(session)]

    by_year: dict[int, list[ClassifiedChange]] = defaultdict(list)
    for c in classified:
        by_year[c.display_year].append(c)

    out: dict[int, list[dict[str, Any]]] = {}
    for year, items in by_year.items():
        elevated: list[dict[str, Any]] = []
        routine_members: list[dict[str, Any]] = []
        groups: dict[str, list[ClassifiedChange]] = defaultdict(list)

        for c in items:
            if c.treatment == "STATE":
                if c.category in resolved.get(year, set()):
                    continue  # absorbed by the state-table diff already shown
                # hedged: setting was edited but the tracked structure didn't move
                actor = c.raw.actor or "A manager"
                noun = "roster" if c.canonical_type == "roster_positions" else "scoring"
                routine_members.append(
                    _detail(
                        c,
                        title=c.human_label,
                        summary=(
                            f"{actor} edited {noun} settings on {_iso_date(c.raw.executed_at)}; "
                            "NFL.com records only that an edit happened, not the values."
                        ),
                        tier="T3",
                        certainty="source_limited",
                        missing_context=True,
                    )
                )
            elif c.event_group_key is not None:
                groups[c.event_group_key].append(c)
            elif c.treatment in {"PASS", "MISSING"}:
                elevated.append(_emit_individual(c))
            else:  # COLLAPSE / HEDGE
                routine_members.append(_member_detail(c))

        for key, cluster in groups.items():
            event, leftovers = _emit_group(key, cluster)
            if event is not None:
                elevated.append(event)
            routine_members.extend(_member_detail(i) for i in leftovers)

        # order: T1, then T2, then the single T3 routine bucket last
        tier_rank = {"T1": 0, "T2": 1, "T3": 2}
        elevated.sort(key=lambda d: (tier_rank.get(d["tier"], 9), d.get("changed_at") or ""))

        if routine_members:
            routine_members.sort(key=lambda d: d.get("changed_at") or "")
            n = len(routine_members)
            elevated.append(
                {
                    "category": "admin",
                    "title": f"{n} routine change{'s' if n != 1 else ''}",
                    "summary": "Routine admin / draft-logistics changes; expand to see each.",
                    "before": None,
                    "after": None,
                    "source": _SOURCE,
                    "certainty": "source_limited",
                    "changed_at": routine_members[-1].get("changed_at"),
                    "participants_joined": None,
                    "participants_left": None,
                    "description_gap": False,
                    "tier": "T3",
                    "human_label": "Routine changes",
                    "phase": None,
                    "event_group_key": f"routine-{year}",
                    "missing_context": False,
                    "members": routine_members,
                    "canonical_type": "routine_bucket",
                }
            )
        out[year] = elevated
    return out
