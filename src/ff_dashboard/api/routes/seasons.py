"""Seasons & standings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found
from ff_pipeline.repository.queries import get_season, get_team

from ff_dashboard.analytics.brackets import season_brackets
from ff_dashboard.analytics.common import displayed_seasons, owner_name_map, require_league
from ff_dashboard.analytics.conferences import official_division_map, season_conferences
from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.current_season import current_season
from ff_dashboard.analytics.efficiency import season_efficiency, season_potential_points
from ff_dashboard.analytics.platform import season_platform_fields
from ff_dashboard.analytics.standings import (
    compute_standings,
    season_summary,
    standings_insights,
    standings_timeline,
)
from ff_dashboard.analytics.weekly_scores import weekly_scores
from ff_dashboard.api.deps import CacheDep, SessionDep  # noqa: TC001 — runtime deps for FastAPI
from ff_dashboard.api.schemas import (
    CurrentSeason,
    Envelope,
    SeasonBracket,
    SeasonConferences,
    SeasonEfficiency,
    SeasonList,
    SeasonListItem,
    SeasonSummary,
    SeasonWeeklyScores,
    Standings,
    StandingsInsights,
    StandingsTimeline,
    TeamRef,
)

router = APIRouter(tags=["seasons"])


@router.get("/v1/seasons", response_model=Envelope[SeasonList])
def list_seasons(session: SessionDep) -> Envelope[SeasonList]:
    league = require_league(session)
    scored = set(seasons_scored(session))
    owners = owner_name_map(session)
    items: list[SeasonListItem] = []
    for s in displayed_seasons(session, league.league_id):
        champion = None
        if s.champion_team_id is not None:
            team = get_team(session, s.champion_team_id)
            if team is not None:
                champion = TeamRef(
                    team_id=team.team_id,
                    team_name=team.team_name,
                    owner_id=team.owner_id,
                    owner_name=owners.get(team.owner_id),
                )
        items.append(
            SeasonListItem(
                season_id=s.season_id,
                season_year=s.year,
                status=s.status,
                is_scored=s.year in scored,
                champion=champion,
                **season_platform_fields(session, s.season_id),
            )
        )
    return Envelope(data=SeasonList(seasons=items), meta=build_meta(session))


# Declared before ``/v1/seasons/{season_id}`` so "current" is not read as an id.
@router.get("/v1/seasons/current", response_model=Envelope[CurrentSeason])
def get_current_season(session: SessionDep) -> Envelope[CurrentSeason]:
    require_league(session)
    return Envelope(data=CurrentSeason(**current_season(session)), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}", response_model=Envelope[SeasonSummary])
def get_season_summary(season_id: int, session: SessionDep) -> Envelope[SeasonSummary]:
    season = get_season(session, season_id)
    if season is None:
        raise not_found(f"No season with id {season_id}")
    data = SeasonSummary(
        **season_summary(session, season), **season_platform_fields(session, season_id)
    )
    return Envelope(data=data, meta=build_meta(session))


def _division_source(
    session: SessionDep, season_id: int, rows: list[dict[str, object]]
) -> str | None:
    """What the rows' division labels are: platform-recorded, stored NFL.com history, or none."""
    season = get_season(session, season_id)
    if season is not None and official_division_map(session, season):
        return "official"
    return "derived" if any(r.get("conference_name") for r in rows) else None


@router.get("/v1/seasons/{season_id}/standings", response_model=Envelope[Standings])
def get_standings(
    season_id: int,
    session: SessionDep,
    cache: CacheDep,
    through_week: int | None = Query(None, ge=1),
) -> Envelope[Standings]:
    data = compute_standings(session, season_id, through_week)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    week = data["through_week"]
    potential = cache.get_or_compute(
        session,
        f"potential_points:{season_id}:{week}",
        lambda: season_potential_points(session, season_id, week),
    )
    uncertain: set[int] = set()
    rows = []
    for row in data["rows"]:
        pp = potential.get(int(row["team_id"])) or {}
        uncertain.update(pp.get("uncertain_weeks") or [])
        rows.append(
            {
                **row,
                "potential_points": pp.get("computed"),
                "potential_points_official": pp.get("official"),
            }
        )
    data = {
        **data,
        "rows": rows,
        "potential_points_uncertain_weeks": sorted(uncertain),
        "division_source": _division_source(session, season_id, rows),
    }
    return Envelope(data=Standings(**data), meta=build_meta(session))


@router.get(
    "/v1/seasons/{season_id}/standings/insights",
    response_model=Envelope[StandingsInsights],
)
def get_standings_insights(
    season_id: int,
    session: SessionDep,
    through_week: int | None = Query(None, ge=1),
) -> Envelope[StandingsInsights]:
    data = standings_insights(session, season_id, through_week)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=StandingsInsights(**data), meta=build_meta(session))


@router.get(
    "/v1/seasons/{season_id}/standings/timeline",
    response_model=Envelope[StandingsTimeline],
)
def get_standings_timeline(season_id: int, session: SessionDep) -> Envelope[StandingsTimeline]:
    data = standings_timeline(session, season_id)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=StandingsTimeline(**data), meta=build_meta(session))


@router.get(
    "/v1/seasons/{season_id}/weekly-scores",
    response_model=Envelope[SeasonWeeklyScores],
)
def get_weekly_scores(season_id: int, session: SessionDep) -> Envelope[SeasonWeeklyScores]:
    data = weekly_scores(session, season_id)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=SeasonWeeklyScores(**data), meta=build_meta(session))


@router.get(
    "/v1/seasons/{season_id}/efficiency",
    response_model=Envelope[SeasonEfficiency],
)
def get_efficiency(season_id: int, session: SessionDep) -> Envelope[SeasonEfficiency]:
    data = season_efficiency(session, season_id)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=SeasonEfficiency(**data), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}/bracket", response_model=Envelope[SeasonBracket])
def get_season_bracket(season_id: int, session: SessionDep) -> Envelope[SeasonBracket]:
    data = season_brackets(session, season_id)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=SeasonBracket(**data), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}/conferences", response_model=Envelope[SeasonConferences])
def get_season_conferences(
    season_id: int,
    session: SessionDep,
    through_week: int | None = Query(None, ge=1),
) -> Envelope[SeasonConferences]:
    data = season_conferences(session, season_id, through_week)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=SeasonConferences(**data), meta=build_meta(session))
