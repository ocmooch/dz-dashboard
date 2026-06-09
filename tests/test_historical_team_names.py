"""Historical fantasy-team display names recovered for period-correct labels."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from ff_dashboard.analytics.historical_team_names import period_team_name


def test_period_team_name_uses_historical_slot_name() -> None:
    team = cast("Any", SimpleNamespace(team_abbrev="10", team_name="London on da Track"))
    assert period_team_name(team, 2018) == "do the SHAWdy lean"
    assert period_team_name(team, 2024) == "Montgomery Burns Football Team"


def test_period_team_name_falls_back_to_db_name_when_unknown() -> None:
    team = cast("Any", SimpleNamespace(team_abbrev="10", team_name="London on da Track"))
    assert period_team_name(team, 2026) == "London on da Track"
