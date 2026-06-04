"""Per-season fantasy-schedule model (``analytics/season_schedule.py``).

The single place that answers "how is *this* season's calendar shaped?" — how
many regular-season weeks, which weeks are the fantasy playoffs, and which week
is the title game. Every metric that needs week structure (season totals, the
records era split, entering records) reads it here instead of hardcoding 14/17.

It is **config-driven**: confirmed historical shapes live in ``_CONFIRMED`` and
are returned with ``is_estimated=False``; everything else is derived from the
season's own DB columns (``regular_season_weeks`` / ``playoff_weeks``) and
marked ``is_estimated=True`` so callers can flag an inferred calendar honestly.

``_CONFIRMED`` is intentionally **empty** until the league's 1-13 → 1-14
season-length switch year is supplied (roadmap input #1). With it empty every
season resolves to its current DB-derived shape, so this is purely additive: no
existing output changes. When the switch year lands, enumerate the affected
pre-switch seasons here and re-run the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from ff_dashboard.analytics.common import regular_season_weeks

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
    from sqlalchemy.orm import Session


class ScheduleSpec(TypedDict):
    """A confirmed/default calendar shape (absolute week numbers)."""

    regular_weeks: int
    playoffs: tuple[int, ...]
    championship: int


@dataclass(frozen=True)
class SeasonSchedule:
    """The fantasy calendar for one season.

    ``regular_weeks`` are weeks ``1..regular_weeks``; ``playoff_weeks`` are the
    fantasy-playoff week numbers (the last of which is ``championship_week``).
    ``is_estimated`` is True whenever the shape came from the DB columns or the
    modern default rather than a confirmed ``_CONFIRMED`` entry.
    """

    season_year: int
    regular_weeks: int
    playoff_weeks: tuple[int, ...]
    championship_week: int
    is_estimated: bool


# The modern (current-era) fantasy calendar: 14-week regular season, a 3-week
# playoff bracket, title game in week 17. Used both as documentation of the
# default shape and as the fallback playoff length when a season's DB
# ``playoff_weeks`` is unset.
_MODERN: ScheduleSpec = {"regular_weeks": 14, "playoffs": (15, 16, 17), "championship": 17}
_MODERN_PLAYOFF_WEEKS = len(_MODERN["playoffs"])

# Confirmed historical overrides keyed by ``season_year``. EMPTY until the user
# supplies the 1-13 → 1-14 switch season (roadmap input #1); then enumerate each
# pre-switch season as ``{"regular_weeks": 13, "playoffs": (14, 15, 16),
# "championship": 16}``.
_CONFIRMED: dict[int, ScheduleSpec] = {}  # TODO(input: season-length switch year)


def modern_schedule(season_year: int) -> SeasonSchedule:
    """The modern default calendar for a season (the ``_MODERN`` shape)."""
    return SeasonSchedule(
        season_year=season_year,
        regular_weeks=_MODERN["regular_weeks"],
        playoff_weeks=_MODERN["playoffs"],
        championship_week=_MODERN["championship"],
        is_estimated=True,
    )


def season_schedule(session: Session, season: Season) -> SeasonSchedule:
    """Resolve the fantasy calendar for ``season``.

    Resolution order:

    1. ``_CONFIRMED[year]`` if present → ``is_estimated=False``.
    2. else derive ``regular_weeks`` from the DB column (falling back to the max
       played week when unset, via :func:`common.regular_season_weeks`) and the
       playoff bracket from the season's ``playoff_weeks`` column, defaulting to
       the modern 3-week bracket when that too is unset → ``is_estimated=True``.
    """
    confirmed = _CONFIRMED.get(season.year)
    if confirmed is not None:
        return SeasonSchedule(
            season_year=season.year,
            regular_weeks=confirmed["regular_weeks"],
            playoff_weeks=confirmed["playoffs"],
            championship_week=confirmed["championship"],
            is_estimated=False,
        )

    regular = regular_season_weeks(session, season)
    n_playoff = int(season.playoff_weeks) if season.playoff_weeks else _MODERN_PLAYOFF_WEEKS
    championship = regular + n_playoff
    playoffs = tuple(range(regular + 1, championship + 1))
    return SeasonSchedule(
        season_year=season.year,
        regular_weeks=regular,
        playoff_weeks=playoffs,
        championship_week=championship,
        is_estimated=True,
    )


def fantasy_week_range(schedule: SeasonSchedule) -> range:
    """The weeks that count as fantasy weeks: ``1..championship_week``."""
    return range(1, schedule.championship_week + 1)


def phase_of_week(schedule: SeasonSchedule, week: int) -> str:
    """Classify a week: ``regular`` | ``playoff`` | ``championship`` | ``out_of_season``."""
    if 1 <= week <= schedule.regular_weeks:
        return "regular"
    if week == schedule.championship_week:
        return "championship"
    if week in schedule.playoff_weeks:
        return "playoff"
    return "out_of_season"
