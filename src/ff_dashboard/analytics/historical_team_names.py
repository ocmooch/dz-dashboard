"""Period-correct fantasy team names (the seam all emitted team names go through).

The Phase 1 DB's ``teams.team_name`` is the season-correct NFL.com name for each
team-season, so these helpers return it. They are kept as one place to route
names through, so a future per-season override has a single home.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Team


# The hardcoded (season, slot) -> name table that used to live here is gone: since
# the upstream owner-identity repair, ``teams.team_name`` in the Phase 1 DB is
# already the period-correct NFL.com name for every past team-season (verified
# 192/192 identical on 2026-11-09), and the repo is public, so league team names
# do not belong in source. The helpers stay as the single seam every analytics
# module routes emitted team names through.
HISTORICAL_TEAM_NAMES: dict[tuple[int, str], str] = {}


def period_team_name_by_slot(
    season_year: int | None, team_abbrev: str | None, fallback: str | None
) -> str | None:
    """Period-correct fantasy team name for a ``(year, slot)``, else ``fallback``.

    The slot is the NFL.com team-slot number carried in ``team_abbrev``. Use this
    overload when only loose columns are in hand (e.g. a ``select(...)`` of
    specific fields) rather than a full ``Team`` ORM object.
    """
    if team_abbrev is None or season_year is None:
        return fallback
    return HISTORICAL_TEAM_NAMES.get((season_year, str(team_abbrev)), fallback)


def period_team_name(team: Team, season_year: int | None = None) -> str | None:
    """Return a period-correct fantasy team name for the team's season.

    The live DB's ``teams.team_name`` carries the current/canonical label after
    owner-identity repair, so a past team-season renders the latest name. This
    restores the season-correct NFL.com slot name. ``season_year`` defaults to
    the team's own ``season.year`` when not supplied.
    """
    if season_year is None:
        season_year = team.season.year
    return period_team_name_by_slot(season_year, team.team_abbrev, team.team_name)
