"""Global typeahead search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query
from ff_pipeline.api._meta import build_meta

from ff_dashboard.analytics.search import global_search
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import Envelope, SearchHit, SearchResults

router = APIRouter(tags=["search"])


@router.get("/v1/search", response_model=Envelope[SearchResults])
def search(
    session: SessionDep,
    q: str = Query(..., min_length=1, description="Search text"),
    limit: int = Query(10, ge=1, le=50),
) -> Envelope[SearchResults]:
    hits = [SearchHit(**hit) for hit in global_search(session, q, limit=limit)]
    return Envelope(
        data=SearchResults(query=q, hits=hits),
        meta=build_meta(session),
    )
