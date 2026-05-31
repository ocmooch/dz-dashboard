"""Draft board & pick-value endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found

from ff_dashboard.analytics.draft import draft_board, draft_value
from ff_dashboard.api.deps import CacheDep, SessionDep  # noqa: TC001 — runtime deps for FastAPI
from ff_dashboard.api.schemas import DraftBoard, DraftValue, Envelope

router = APIRouter(tags=["draft"])


@router.get("/v1/seasons/{season_id}/draft", response_model=Envelope[DraftBoard])
def get_draft_board(season_id: int, session: SessionDep, cache: CacheDep) -> Envelope[DraftBoard]:
    data = cache.get_or_compute(
        session, f"draft_board:{season_id}", lambda: draft_board(session, season_id)
    )
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=DraftBoard(**data), meta=build_meta(session))


@router.get("/v1/seasons/{season_id}/draft/value", response_model=Envelope[DraftValue])
def get_draft_value(season_id: int, session: SessionDep, cache: CacheDep) -> Envelope[DraftValue]:
    data = cache.get_or_compute(
        session, f"draft_value:{season_id}", lambda: draft_value(session, season_id)
    )
    if data is None:
        raise not_found(f"No season with id {season_id}")
    return Envelope(data=DraftValue(**data), meta=build_meta(session))
