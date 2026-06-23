"""Players & stats endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found
from ff_pipeline.repository.queries import (
    get_player,
    get_season_by_year,
)

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.players import (
    availability,
    list_player_index,
    ownership_timeline,
    player_insights,
    player_scoring,
)
from ff_dashboard.analytics.stats import season_totals, top_scorers
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import (
    Envelope,
    PlayerAvailability,
    PlayerIndex,
    PlayerIndexRow,
    PlayerInsights,
    PlayerOut,
    PlayerOwnership,
    PlayerScoring,
    SeasonTotal,
    SeasonTotals,
    TopScorer,
    TopScorers,
)

router = APIRouter(tags=["players"])


@router.get("/v1/players", response_model=Envelope[PlayerIndex])
def list_players(
    session: SessionDep,
    name: str | None = None,
    position: str | None = None,
    nfl_team: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Envelope[PlayerIndex]:
    rows = list_player_index(
        session,
        name=name,
        position=position,
        nfl_team=nfl_team,
        scope="league",
        limit=limit,
        offset=offset,
    )
    return Envelope(
        data=PlayerIndex(
            players=[PlayerIndexRow(**r) for r in rows],
            limit=limit,
            offset=offset,
        ),
        meta=build_meta(session),
    )


@router.get("/v1/players/{player_id}", response_model=Envelope[PlayerOut])
def get_player_detail(player_id: int, session: SessionDep) -> Envelope[PlayerOut]:
    player = get_player(session, player_id)
    if player is None:
        raise not_found(f"No player with id {player_id}")
    return Envelope(data=PlayerOut.model_validate(player), meta=build_meta(session))


@router.get("/v1/players/{player_id}/scoring", response_model=Envelope[PlayerScoring])
def get_player_scoring(
    player_id: int, session: SessionDep, season: int = Query(..., ge=1999)
) -> Envelope[PlayerScoring]:
    data = player_scoring(session, player_id, season)
    if data is None:
        raise not_found(f"No player with id {player_id}")
    return Envelope(data=PlayerScoring(**data), meta=build_meta(session))


@router.get("/v1/players/{player_id}/ownership", response_model=Envelope[PlayerOwnership])
def get_player_ownership(player_id: int, session: SessionDep) -> Envelope[PlayerOwnership]:
    data = ownership_timeline(session, player_id)
    if data is None:
        raise not_found(f"No player with id {player_id}")
    return Envelope(data=PlayerOwnership(**data), meta=build_meta(session))


@router.get("/v1/players/{player_id}/insights", response_model=Envelope[PlayerInsights])
def get_player_insights(player_id: int, session: SessionDep) -> Envelope[PlayerInsights]:
    data = player_insights(session, player_id)
    if data is None:
        raise not_found(f"No player with id {player_id}")
    return Envelope(data=PlayerInsights(**data), meta=build_meta(session))


@router.get("/v1/players/{player_id}/availability", response_model=Envelope[PlayerAvailability])
def get_player_availability(
    player_id: int, session: SessionDep, season: int = Query(..., ge=1999)
) -> Envelope[PlayerAvailability]:
    data = availability(session, player_id, season)
    if data is None:
        raise not_found(f"No player with id {player_id}")
    return Envelope(data=PlayerAvailability(**data), meta=build_meta(session))


@router.get("/v1/stats/top-scorers", response_model=Envelope[TopScorers])
def get_top_scorers(
    session: SessionDep,
    season: int = Query(..., ge=1999),
    week: int | None = Query(None, ge=1),
    position: str | None = None,
    limit: int = Query(25, ge=1, le=500),
) -> Envelope[TopScorers]:
    rows = top_scorers(session, season_year=season, week=week, position=position, limit=limit)
    return Envelope(
        data=TopScorers(
            season_year=season,
            week=week,
            position=position,
            scorers=[TopScorer(**r) for r in rows],
        ),
        meta=build_meta(session),
    )


@router.get("/v1/stats/season-totals", response_model=Envelope[SeasonTotals])
def get_season_totals(
    session: SessionDep,
    season: int = Query(..., ge=1999),
    position: str | None = None,
) -> Envelope[SeasonTotals]:
    league = require_league(session)
    season_obj = get_season_by_year(session, league.league_id, season)
    rows = season_totals(session, season_obj, position=position) if season_obj is not None else []
    return Envelope(
        data=SeasonTotals(
            season_year=season,
            position=position,
            totals=[SeasonTotal(**r) for r in rows],
        ),
        meta=build_meta(session),
    )
