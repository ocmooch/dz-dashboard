"""Rivalries endpoints — league-wide insight bands for the ``/rivalries`` page."""

from __future__ import annotations

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.rivalries import rivalry_insights
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import Envelope, RivalryInsights

router = APIRouter(tags=["rivalries"])


@router.get("/v1/rivalries/insights", response_model=Envelope[RivalryInsights])
def get_rivalry_insights(session: SessionDep) -> Envelope[RivalryInsights]:
    require_league(session)
    return Envelope(data=RivalryInsights(**rivalry_insights(session)), meta=build_meta(session))
