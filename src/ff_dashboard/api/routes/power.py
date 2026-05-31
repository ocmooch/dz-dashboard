"""Power-ranking endpoints (current + over-time)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found

from ff_dashboard.analytics.power import power_ranking, power_timeline
from ff_dashboard.api.deps import CacheDep, SessionDep  # noqa: TC001 — runtime deps for FastAPI
from ff_dashboard.api.schemas import Envelope, PowerRanking, PowerTimeline

router = APIRouter(tags=["power"])


@router.get("/v1/seasons/{season_id}/power", response_model=Envelope[PowerRanking])
def get_power_ranking(
    season_id: int,
    session: SessionDep,
    cache: CacheDep,
    through_week: int | None = Query(None, ge=1),
) -> Envelope[PowerRanking]:
    data = cache.get_or_compute(
        session,
        f"power:{season_id}:{through_week}",
        lambda: power_ranking(session, season_id, through_week),
    )
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=PowerRanking(**data), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}/power/timeline", response_model=Envelope[PowerTimeline])
def get_power_timeline(
    season_id: int, session: SessionDep, cache: CacheDep
) -> Envelope[PowerTimeline]:
    data = cache.get_or_compute(
        session, f"power_timeline:{season_id}", lambda: power_timeline(session, season_id)
    )
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=PowerTimeline(**data), meta=build_meta(session))
