"""Unit tests for the shared roster-snapshot semantics.

These guard the single source of truth used by the box score, the team-page
roster, and the roster-move reconstruction to decide whether a week's roster is
an authoritative weekly capture or a non-authoritative ``audit`` reconstruction.
"""

from __future__ import annotations

from types import SimpleNamespace

from ff_dashboard.analytics.roster_snapshots import (
    is_reconstructed_week,
    reconstructed_note,
    snapshot_kind,
)


def test_snapshot_kind_reads_and_trims_extra_data() -> None:
    assert snapshot_kind(SimpleNamespace(extra_data={"snapshot_kind": "history"})) == "history"
    assert snapshot_kind(SimpleNamespace(extra_data={"snapshot_kind": " audit "})) == "audit"
    # Missing / blank / absent extra_data → None (not evidence of audit).
    assert snapshot_kind(SimpleNamespace(extra_data={"snapshot_kind": "  "})) is None
    assert snapshot_kind(SimpleNamespace(extra_data={})) is None
    assert snapshot_kind(SimpleNamespace(extra_data=None)) is None


def test_is_reconstructed_week_only_when_all_known_kinds_are_audit() -> None:
    assert is_reconstructed_week(["audit", "audit", "audit"]) is True
    # Rows without a stamped snapshot_kind don't count against an all-audit week.
    assert is_reconstructed_week(["audit", None, "audit"]) is True
    # Any authoritative capture means drift is player-specific, not systemic.
    assert is_reconstructed_week(["audit", "history"]) is False
    assert is_reconstructed_week(["audit", "draft"]) is False
    assert is_reconstructed_week(["audit", "pre_kickoff"]) is False
    assert is_reconstructed_week(["history", "history"]) is False
    # No known snapshot kinds at all → not flagged as reconstructed.
    assert is_reconstructed_week([None, None]) is False
    assert is_reconstructed_week([]) is False


def test_reconstructed_note_names_the_week() -> None:
    note = reconstructed_note(1)
    assert "Week-1" in note
    assert "audit snapshot" in note
