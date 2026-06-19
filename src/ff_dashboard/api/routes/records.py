"""Records book endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta

from ff_dashboard.analytics.draft import best_worst_picks
from ff_dashboard.analytics.records import championships, records_book
from ff_dashboard.api.deps import CacheDep, SessionDep  # noqa: TC001 — runtime deps for FastAPI
from ff_dashboard.api.schemas import ChampionshipHistory, DraftRecords, Envelope, RecordsBook

router = APIRouter(tags=["records"])


@router.get("/v1/records", response_model=Envelope[RecordsBook])
def get_records(session: SessionDep, cache: CacheDep) -> Envelope[RecordsBook]:
    data = cache.get_or_compute(session, "records_book", lambda: records_book(session))
    return Envelope(data=RecordsBook(**data), meta=build_meta(session))


@router.get("/v1/records/championships", response_model=Envelope[ChampionshipHistory])
def get_championships(session: SessionDep) -> Envelope[ChampionshipHistory]:
    return Envelope(data=ChampionshipHistory(**championships(session)), meta=build_meta(session))


@router.get("/v1/records/draft", response_model=Envelope[DraftRecords])
def get_draft_records(session: SessionDep, cache: CacheDep) -> Envelope[DraftRecords]:
    data = cache.get_or_compute(
        session, "draft_records", lambda: best_worst_picks(session, cache=cache)
    )
    return Envelope(data=DraftRecords(**data), meta=build_meta(session))
