"""Cross-era aggregation rules (Sleeper D4, ``docs/sleeper/01`` §5).

One place for how a number that spans seasons treats seasons that differ:

* **Counted seasons.** A final season counts every week. An in-progress season counts only its
  finalized weeks (the D3 rule: the unfinished week is unscored), so a cross-season payload that
  includes it is *partial* and says "through week N".
* **Scoring eras.** Contiguous seasons with the same stored scoring rules. A records row carries
  its era so a 2012 score and a 2026 score are compared with the rules marked, never silently.
  A season with no stored rules joins no era (``None``): never guessed.
* **Activity.** Moves only (add / drop / waiver / trade with a player). Lineup and setting logs,
  failed claims and player-less pick/FAAB legs are not moves.
* **FAAB.** Raw dollars per season; cross-era comparisons use % of that season's budget.
* **Aggregation note.** ``{used_seasons, excluded_seasons, partial_seasons, reason}`` on a payload
  that excluded or partially counted a season; ``None`` when it did neither, so legacy payloads
  are unchanged.

Read-only; the pure helpers take plain values.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries
from ff_pipeline.repository.models import ScoringRule, Season, Team
from sqlalchemy import select

from ff_dashboard.analytics.common import played_season_ids
from ff_dashboard.analytics.platform import week_state

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session

#: Capability states that have something to show (``not_yet`` / ``not_on_platform`` /
#: ``not_used`` do not).
SHOWABLE_STATES = frozenset({"available", "partial", "derived"})

#: Transaction types that move a player on or off a roster.
MOVE_TYPES = frozenset({"free_agent_add", "waiver_add", "drop", "trade"})

#: Sleeper's lost waiver claim; legacy rows carry ``status`` NULL.
FAILED_STATUS = "failed"

#: ``aggregation_note.reason`` codes (copy lives in the SPA's ``lib/platform.ts``).
REASON_IN_PROGRESS = "in_progress_partial"
REASON_SEASON_TOTALS = "season_totals_exclude_in_progress"


# ── seasons ──────────────────────────────────────────────────────────────────


def seasons_with(session: Session, capability: str) -> set[int]:
    """season_ids (played) whose ``capability`` has something to show."""
    out: set[int] = set()
    for sid in played_season_ids(session):
        caps = queries.season_capabilities(session, sid) or {}
        cap = caps.get(capability)
        if cap is not None and cap.state in SHOWABLE_STATES:
            out.add(sid)
    return out


def counted_seasons(session: Session) -> dict[int, int | None]:
    """Played ``season_id -> through_week``: ``None`` for a final season, else the last finalized
    week of the in-progress season (``0`` when no week is final yet)."""
    out: dict[int, int | None] = {}
    for sid in sorted(played_season_ids(session)):
        weeks = week_state(session, sid)
        out[sid] = None if weeks["is_final"] else int(weeks["last_finalized_week"] or 0)
    return out


def _season_years(session: Session) -> dict[int, int]:
    return {int(s): int(y) for s, y in session.execute(select(Season.season_id, Season.year)).all()}


def partial_seasons(
    session: Session, season_ids: Iterable[int] | None = None
) -> list[dict[str, int]]:
    """``[{season_year, through_week}]`` for in-progress seasons (optionally among ``season_ids``)."""
    years = _season_years(session)
    scope = None if season_ids is None else {int(s) for s in season_ids}
    return [
        {"season_year": years[sid], "through_week": through}
        for sid, through in counted_seasons(session).items()
        if through is not None and (scope is None or sid in scope)
    ]


def owner_season_ids(session: Session, owner_id: int) -> set[int]:
    rows = session.execute(select(Team.season_id).where(Team.owner_id == owner_id)).scalars()
    return {int(s) for s in rows}


# ── scoring eras ─────────────────────────────────────────────────────────────


def _rules_signature(rules: Iterable[ScoringRule]) -> tuple[tuple[str, ...], ...]:
    """A season's whole rule set, order-free. ``repr`` keeps None-vs-str sortable."""
    return tuple(
        sorted(
            tuple(
                repr(v)
                for v in (
                    r.category,
                    r.stat_key,
                    r.threshold_min,
                    r.threshold_max,
                    r.points_per_unit,
                    r.unit_size,
                    r.flat_points,
                    r.raw_text,
                )
            )
            for r in rules
        )
    )


EN_DASH = "\u2013"


def _era_label(start: int, end: int | None) -> str:
    """``"2011<en dash>2020"``, ``"2010"``, or open-ended ``"2026<en dash>"``."""
    if end is None:
        return f"{start}{EN_DASH}"
    return str(start) if start == end else f"{start}{EN_DASH}{end}"


def scoring_eras(session: Session) -> dict[int, dict[str, Any] | None]:
    """``season_year -> {era_id, label, start, end}`` for played seasons; ``None`` without rules.

    Contiguous played seasons with an identical stored rule set share an era. The era holding an
    in-progress season is open-ended (``end`` None, label ``"2026-"`` with an en dash)."""
    played = played_season_ids(session)
    seasons = [
        s
        for s in session.execute(select(Season).order_by(Season.year)).scalars()
        if int(s.season_id) in played
    ]
    by_season: dict[int, list[ScoringRule]] = {}
    for rule in session.execute(select(ScoringRule)).scalars():
        by_season.setdefault(int(rule.season_id), []).append(rule)
    in_progress = {sid for sid, t in counted_seasons(session).items() if t is not None}

    groups: list[list[Season]] = []
    prev_sig: tuple[tuple[str, ...], ...] | None = None
    out: dict[int, dict[str, Any] | None] = {}
    for s in seasons:
        rules = by_season.get(int(s.season_id))
        if not rules:
            out[int(s.year)] = None
            prev_sig = None
            continue
        sig = _rules_signature(rules)
        if prev_sig is not None and sig == prev_sig:
            groups[-1].append(s)
        else:
            groups.append([s])
        prev_sig = sig

    for era_id, group in enumerate(groups, start=1):
        start = int(group[0].year)
        open_ended = any(int(s.season_id) in in_progress for s in group)
        end = None if open_ended else int(group[-1].year)
        era = {"era_id": era_id, "label": _era_label(start, end), "start": start, "end": end}
        for s in group:
            out[int(s.year)] = era
    return out


def scoring_era_count(eras: dict[int, dict[str, Any] | None]) -> int:
    """How many distinct scoring eras the played seasons span (rule-less seasons don't count)."""
    return len({e["era_id"] for e in eras.values() if e is not None})


# ── activity + FAAB ──────────────────────────────────────────────────────────


def is_failed_claim(txn: Any) -> bool:
    return getattr(txn, "status", None) == FAILED_STATUS


def is_move(txn: Any) -> bool:
    """A roster move: add / drop / waiver / trade that happened and names a player.

    Not a move: lineup and setting logs, draft picks, a failed claim, a player-less pick/FAAB leg."""
    return (
        getattr(txn, "transaction_type", None) in MOVE_TYPES
        and not is_failed_claim(txn)
        and getattr(txn, "player_id", None) is not None
    )


def pct_of_budget(spend: float | None, budget: float | None) -> float | None:
    """Spend as a share of that season's budget; ``None`` (never 0) when either is unknown."""
    if spend is None or budget is None or budget <= 0:
        return None
    return round(float(spend) / float(budget), 4)


def normalize_within_season(
    rows: list[dict[str, Any]], field: str, key: str = "season_id"
) -> list[dict[str, Any]]:
    """Copies of ``rows`` with ``f"{field}_z"``: the z-score within the row's season.

    ``None`` when the value is missing, the season has fewer than two values, or no spread."""
    groups: dict[Any, list[float]] = {}
    for r in rows:
        if r.get(field) is not None:
            groups.setdefault(r.get(key), []).append(float(r[field]))
    out: list[dict[str, Any]] = []
    for r in rows:
        values = groups.get(r.get(key), [])
        z: float | None = None
        if r.get(field) is not None and len(values) >= 2:
            sd = pstdev(values)
            if sd:
                z = round((float(r[field]) - mean(values)) / sd, 4)
        out.append({**r, f"{field}_z": z})
    return out


# ── the note ─────────────────────────────────────────────────────────────────


def aggregation_note(
    used: Iterable[int],
    excluded: Iterable[int],
    reason: str,
    partial: Iterable[dict[str, int]] | None = None,
) -> dict[str, Any] | None:
    """The payload's aggregation note, or ``None`` when nothing was excluded or partial."""
    excluded_l = sorted({int(y) for y in excluded})
    partial_l = sorted(partial or [], key=lambda p: p["season_year"])
    if not excluded_l and not partial_l:
        return None
    return {
        "used_seasons": sorted({int(y) for y in used}),
        "excluded_seasons": excluded_l,
        "partial_seasons": partial_l,
        "reason": reason,
    }


def partial_note(
    session: Session, season_ids: Iterable[int] | None = None
) -> dict[str, Any] | None:
    """Note for a sum-across-eras payload over ``season_ids`` (default: every played season):
    an in-progress season is counted through its last final week."""
    years = _season_years(session)
    scope = played_season_ids(session) if season_ids is None else set(season_ids)
    scope &= played_season_ids(session)
    return aggregation_note(
        used=(years[s] for s in scope),
        excluded=(),
        reason=REASON_IN_PROGRESS,
        partial=partial_seasons(session, scope),
    )
