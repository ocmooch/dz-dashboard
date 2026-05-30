"""Matchups & box-score endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found

from ff_dashboard.analytics.matchups import box_score, week_matchups
from ff_dashboard.api.deps import CacheDep, SessionDep  # noqa: TC001 — runtime deps for FastAPI
from ff_dashboard.api.schemas import BoxScore, Envelope, WeekMatchups

router = APIRouter(tags=["matchups"])


@router.get(
    "/v1/seasons/{season_id}/weeks/{week}/matchups",
    response_model=Envelope[WeekMatchups],
)
def get_week_matchups(
    season_id: int, week: int, session: SessionDep, cache: CacheDep
) -> Envelope[WeekMatchups]:
    data = cache.get_or_compute(
        session,
        f"week_matchups:{season_id}:{week}",
        lambda: week_matchups(session, season_id, week),
    )
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=WeekMatchups(**data), meta=build_meta(session))


@router.get("/v1/matchups/{matchup_id}/box-score", response_model=Envelope[BoxScore])
def get_box_score(matchup_id: int, session: SessionDep, cache: CacheDep) -> Envelope[BoxScore]:
    data = cache.get_or_compute(
        session, f"box_score:{matchup_id}", lambda: box_score(session, matchup_id)
    )
    if data is None:
        raise not_found(f"No matchup with id {matchup_id}")
    return Envelope(data=BoxScore(**data), meta=build_meta(session))
