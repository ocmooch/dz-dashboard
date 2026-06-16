"""Shared roster-snapshot semantics (``team_rosters.extra_data.snapshot_kind``).

Phase 1 stores roster snapshots at grain ``(season, week, team, player)`` but
from two very different sources, tagged by ``snapshot_kind``:

* ``history`` / ``draft`` — reconstructed from NFL.com's per-week finished-game
  (and draft) pages. Week-accurate.
* ``pre_kickoff`` — a live league-page capture taken Sunday morning *of* that
  week, i.e. the locked weekly lineup. Week-accurate.
* ``audit`` — a live league-page capture taken at any other time. The live
  roster page is **not week-aware** (it always returns *today's* roster), so an
  off-time ``audit`` sync stamps the current roster onto whatever week slot it
  was pointed at. **Not week-accurate.**

A week whose *only* snapshot kind is ``audit`` is therefore a reconstruction,
not the true week-N roster: its per-player roster→team attribution and lineup
slots are approximate and disagree wholesale with transaction history. Any
consumer that reads a per-week roster (box score, team-page roster, week-over-
week roster-move diffs) must not treat such a week as authoritative — this
module is the one place that decides that, so the rule stays consistent across
all of them.

This is a class keyed on ``snapshot_kind``, never on a hardcoded year: today the
all-``audit`` weeks happen to be 2025-W1 and 2026-W1, but the check is data-
driven so it keeps working as the pipeline re-ingests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

# The non-authoritative live-capture kind (see module docstring).
AUDIT_SNAPSHOT_KIND = "audit"


def snapshot_kind(roster_row: Any) -> str | None:
    """The ``snapshot_kind`` stamped on a ``team_rosters`` row, or ``None``.

    ``None`` for older loads that didn't stamp one — those are ignored when
    judging whether a week is reconstructed (absence is not evidence of audit).
    """
    extra = roster_row.extra_data or {}
    value = extra.get("snapshot_kind")
    return value.strip() if isinstance(value, str) and value.strip() else None


def is_reconstructed_week(snapshot_kinds: Iterable[str | None]) -> bool:
    """True when a week's whole roster is a reconstructed audit snapshot.

    Only when *every known* snapshot kind is ``audit``: a mix that includes any
    authoritative (``history`` / ``draft`` / ``pre_kickoff``) row means the week
    has real weekly data and any drift is player-specific, not systemic. Rows
    with no stamped kind are ignored.
    """
    known = [k for k in snapshot_kinds if k]
    return bool(known) and all(k == AUDIT_SNAPSHOT_KIND for k in known)


def reconstructed_note(week: int) -> str:
    """The single team-level caveat shown in place of per-player drift flags."""
    return (
        f"Week-{week} lineup is reconstructed from a roster-audit snapshot; "
        "player-to-team attribution and lineup slots are approximate."
    )
