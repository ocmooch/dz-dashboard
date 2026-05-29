"""Pydantic response models for the dashboard analytics API.

The success envelope, ``Meta``, and ``ErrorBody`` are reused verbatim from
Phase 1 (``ff_pipeline.api.schemas``) so the dashboard's contract is identical
to the read API — one source of truth, no copy-drift. Everything below is
analytics-specific and additive.
"""

from __future__ import annotations

from ff_pipeline.api.schemas import (
    Envelope,
    ErrorBody,
    HealthResponse,
    Meta,
)
from pydantic import BaseModel

__all__ = [
    "Coverage",
    "Envelope",
    "ErrorBody",
    "HealthResponse",
    "LatestRun",
    "Meta",
    "MetaResponse",
]


# ---------------------------------------------------------------------------
# Meta / coverage (powers the "data as of" indicator + gap banners)
# ---------------------------------------------------------------------------


class LatestRun(BaseModel):
    run_id: int | None = None
    status: str | None = None
    mode: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class Coverage(BaseModel):
    """What in the database is trustworthy, partial, or absent.

    Mirrors the reliability map in ``docs/03_DATA_ACCESS.md`` so the frontend
    can render honest gap affordances rather than fabricated zeros.
    """

    seasons_present: list[int]
    seasons_scored: list[int]
    scored_year_min: int | None = None
    scored_year_max: int | None = None
    reconstruction_complete: bool
    availability_current_season_only: bool = True
    dst_scoring_complete: bool = False


class MetaResponse(BaseModel):
    latest_run: LatestRun
    coverage: Coverage
