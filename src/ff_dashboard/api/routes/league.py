"""League-history endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta

from ff_dashboard.analytics.commissioners import commissioner_history
from ff_dashboard.analytics.league_history import (
    league_eras,
    league_overview,
    league_stories,
    league_timeline,
    manager_directory,
)
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 - runtime dep for FastAPI
from ff_dashboard.api.schemas import (
    CommissionerTerm,
    Envelope,
    LeagueEras,
    LeagueOverview,
    LeagueStories,
    LeagueTimeline,
    ManagerDirectory,
)

router = APIRouter(tags=["league"])


@router.get("/v1/league/overview", response_model=Envelope[LeagueOverview])
def get_league_overview(session: SessionDep) -> Envelope[LeagueOverview]:
    overview = league_overview(session)
    terms = [CommissionerTerm(**asdict(t)) for t in commissioner_history(session)]
    return Envelope(
        data=LeagueOverview(**overview, commissioners=terms),
        meta=build_meta(session),
    )


@router.get("/v1/league/timeline", response_model=Envelope[LeagueTimeline])
def get_league_timeline(session: SessionDep) -> Envelope[LeagueTimeline]:
    return Envelope(data=LeagueTimeline(**league_timeline(session)), meta=build_meta(session))


@router.get("/v1/league/eras", response_model=Envelope[LeagueEras])
def get_league_eras(session: SessionDep) -> Envelope[LeagueEras]:
    return Envelope(data=LeagueEras(**league_eras(session)), meta=build_meta(session))


@router.get("/v1/league/stories", response_model=Envelope[LeagueStories])
def get_league_stories(session: SessionDep) -> Envelope[LeagueStories]:
    return Envelope(data=LeagueStories(**league_stories(session)), meta=build_meta(session))


@router.get("/v1/league/managers", response_model=Envelope[ManagerDirectory])
def get_manager_directory(session: SessionDep) -> Envelope[ManagerDirectory]:
    return Envelope(data=ManagerDirectory(**manager_directory(session)), meta=build_meta(session))
