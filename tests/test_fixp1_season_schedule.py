"""fix-P1 / F-32 — the per-season fantasy-schedule model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Season

import ff_dashboard.analytics.season_schedule as ss
from ff_dashboard.analytics.season_schedule import (
    fantasy_week_range,
    modern_schedule,
    phase_of_week,
    season_schedule,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_phase_of_week_modern() -> None:
    sched = modern_schedule(2024)
    assert phase_of_week(sched, 1) == "regular"
    assert phase_of_week(sched, 14) == "regular"
    assert phase_of_week(sched, 15) == "playoff"
    assert phase_of_week(sched, 16) == "playoff"
    assert phase_of_week(sched, 17) == "championship"
    assert phase_of_week(sched, 18) == "out_of_season"


def test_fantasy_week_range_modern() -> None:
    assert fantasy_week_range(modern_schedule(2024)) == range(1, 18)


def test_estimated_from_db_columns(session: Session) -> None:
    # The fixture season carries regular_season_weeks=2, playoff_weeks=1, so the
    # bracket derives to a single playoff week (week 3) and the model flags it
    # as estimated (no confirmed override).
    s = session.get(Season, KNOWN["season_id"][2016])
    assert s is not None
    sched = season_schedule(session, s)
    assert sched.regular_weeks == 2
    assert sched.playoff_weeks == (3,)
    assert sched.championship_week == 3
    assert sched.is_estimated is True


def test_confirmed_override_flips_estimated(session: Session, monkeypatch: object) -> None:
    # Injecting a confirmed entry proves the switch-year path works before the
    # real value lands: estimated flips False and the 13/16 shape is used.
    monkeypatch.setattr(  # type: ignore[attr-defined]
        ss,
        "_CONFIRMED",
        {2016: {"regular_weeks": 13, "playoffs": (14, 15, 16), "championship": 16}},
    )
    s = session.get(Season, KNOWN["season_id"][2016])
    assert s is not None
    sched = season_schedule(session, s)
    assert sched.regular_weeks == 13
    assert sched.playoff_weeks == (14, 15, 16)
    assert sched.championship_week == 16
    assert sched.is_estimated is False


def test_null_regular_weeks_falls_back_without_raising(session: Session) -> None:
    # A season whose regular_season_weeks (and playoff_weeks) are unset must fall
    # back to the max-played week (0 for a season with no matchups) and not raise.
    ghost = Season(league_id="DZTEST", year=1999, regular_season_weeks=None, playoff_weeks=None)
    sched = season_schedule(session, ghost)
    assert sched.regular_weeks == 0
    assert sched.is_estimated is True
