"""Seasons & standings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found
from ff_pipeline.repository.queries import get_season, get_team, list_seasons_for_league

from ff_dashboard.analytics.common import owner_name_map, require_league
from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.standings import (
    compute_standings,
    season_summary,
    standings_timeline,
)
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import (
    Envelope,
    SeasonList,
    SeasonListItem,
    SeasonSummary,
    Standings,
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
    for s in list_seasons_for_league(session, league.league_id):
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
            )
        )
    return Envelope(data=SeasonList(seasons=items), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}", response_model=Envelope[SeasonSummary])
def get_season_summary(season_id: int, session: SessionDep) -> Envelope[SeasonSummary]:
    season = get_season(session, season_id)
    if season is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=SeasonSummary(**season_summary(session, season)), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}/standings", response_model=Envelope[Standings])
def get_standings(
    season_id: int,
    session: SessionDep,
    through_week: int | None = Query(None, ge=1),
) -> Envelope[Standings]:
    data = compute_standings(session, season_id, through_week)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=Standings(**data), meta=build_meta(session))


@router.get(
    "/v1/seasons/{season_id}/standings/timeline",
    response_model=Envelope[StandingsTimeline],
)
def get_standings_timeline(season_id: int, session: SessionDep) -> Envelope[StandingsTimeline]:
    data = standings_timeline(session, season_id)
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=StandingsTimeline(**data), meta=build_meta(session))
