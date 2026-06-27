"""Lab endpoints — experimental, lab-namespaced surfaces proving out against real data.

The non-viz parallel to the web Viz Lab: ``/v1/lab/insights/{season_id}`` serves the
insight primitives (``analytics/insights.py``). Kept under ``/v1/lab`` so it reads as
clearly experimental, separate from the dashboard's permanent contract.
"""

from __future__ import annotations

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.insights import season_insights
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import Envelope, LabInsights

router = APIRouter(tags=["lab"])


@router.get("/v1/lab/insights/{season_id}", response_model=Envelope[LabInsights])
def get_lab_insights(season_id: int, session: SessionDep) -> Envelope[LabInsights]:
    require_league(session)
    return Envelope(
        data=LabInsights(**season_insights(session, season_id)), meta=build_meta(session)
    )
