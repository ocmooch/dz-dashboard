"""``GET /health`` (liveness) and ``GET /v1/meta`` (data freshness + coverage)."""

from __future__ import annotations

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta
from ff_pipeline.repository.queries import latest_pipeline_run

from ff_dashboard.analytics.coverage import compute_coverage, compute_coverage_matrix
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import (
    Coverage,
    CoverageMatrix,
    Envelope,
    HealthResponse,
    LatestRun,
    MetaResponse,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/v1/meta", response_model=Envelope[MetaResponse], tags=["meta"])
def meta(session: SessionDep) -> Envelope[MetaResponse]:
    run = latest_pipeline_run(session)
    latest = LatestRun(
        run_id=run.run_id if run else None,
        status=run.status if run else None,
        mode=run.mode if run else None,
        started_at=run.started_at.isoformat() if run and run.started_at else None,
        finished_at=run.finished_at.isoformat() if run and run.finished_at else None,
    )
    data = MetaResponse(
        latest_run=latest,
        coverage=Coverage(**compute_coverage(session)),
    )
    return Envelope(data=data, meta=build_meta(session))


@router.get("/v1/meta/coverage", response_model=Envelope[CoverageMatrix], tags=["meta"])
def coverage_matrix(session: SessionDep) -> Envelope[CoverageMatrix]:
    return Envelope(
        data=CoverageMatrix(**compute_coverage_matrix(session)), meta=build_meta(session)
    )
