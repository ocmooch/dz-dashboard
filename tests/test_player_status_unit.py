"""Unit tests for ``analytics/player_status`` — the played-vs-status classifier.

The rule under test: a player with proof of having played must never surface an
availability / roster status (IA/IR/SUS/…); game-time injury designations
(Q/D/P) are compatible with playing and a player who did not play keeps any
status. Covers the live-DB universe (IA, IR, NFI-R, Q, SUS) plus the asymmetric
default (unknown status → incompatible).
"""

from __future__ import annotations

import pytest

from ff_dashboard.analytics.player_status import (
    is_compatible_with_play,
    should_suppress_status,
)


@pytest.mark.parametrize(
    "status",
    ["Q", "Questionable", "D", "Doubtful", "P", "Probable", "q", " questionable "],
)
def test_game_time_designations_are_compatible(status: str) -> None:
    assert is_compatible_with_play(status) is True


@pytest.mark.parametrize(
    "status",
    # The live-DB universe of incompatible statuses plus the owner's broader list.
    ["IA", "Inactive", "IR", "Injured Reserve", "SUS", "Suspended", "NFI-R", "PUP", "OUT", "DNP"],
)
def test_availability_statuses_are_incompatible(status: str) -> None:
    assert is_compatible_with_play(status) is False


def test_missing_status_is_compatible() -> None:
    # Nothing to suppress when there is no status at all.
    assert is_compatible_with_play(None) is True
    assert is_compatible_with_play("") is True
    assert is_compatible_with_play("   ") is True


def test_unknown_status_defaults_to_incompatible() -> None:
    # An unfamiliar status on a player we can prove played is suppressed, not
    # shown — a wrong did-not-play badge is the failure we are fixing.
    assert is_compatible_with_play("MYSTERY") is False


def test_suppress_only_when_played_and_incompatible() -> None:
    assert should_suppress_status("IA", played=True) is True
    assert should_suppress_status("Inactive", played=True) is True
    # Compatible designation: never suppressed, even when played.
    assert should_suppress_status("Q", played=True) is False
    # Did not play: the badge is the honest explanation, never suppressed.
    assert should_suppress_status("IA", played=False) is False
    # No status: nothing to suppress.
    assert should_suppress_status(None, played=True) is False
