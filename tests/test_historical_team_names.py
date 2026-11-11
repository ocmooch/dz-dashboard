"""Period-correct team names: the DB name is already season-correct (pass-through)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from ff_dashboard.analytics.historical_team_names import (
    period_team_name,
    period_team_name_by_slot,
)


def test_period_team_name_returns_the_db_name() -> None:
    team = cast("Any", SimpleNamespace(team_abbrev="10", team_name="Team 010"))
    assert period_team_name(team, 2018) == "Team 010"
    assert period_team_name(team, 2026) == "Team 010"


def test_period_team_name_by_slot_returns_the_fallback() -> None:
    assert period_team_name_by_slot(2018, "10", "Team 010") == "Team 010"
    assert period_team_name_by_slot(None, "10", "Team 010") == "Team 010"
    assert period_team_name_by_slot(2018, None, None) is None
