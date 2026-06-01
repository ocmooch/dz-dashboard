"""FastAPI dependency-injection wiring for the dashboard.

Routes pull a read-only ``Session`` via ``SessionDep`` and the process cache
via ``CacheDep``. Both the engine and the cache live on ``app.state`` so tests
can bind a temp-file engine and a fresh cache without monkey-patching modules
(the same pattern Phase 1 uses).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Engine

    from ff_dashboard.cache import AnalyticsCache


def get_session(request: Request) -> Iterator[Session]:
    """Yield a read-only SQLAlchemy session bound to the app's engine."""
    engine: Engine = request.app.state.engine
    with Session(engine) as session:
        yield session


def get_cache(request: Request) -> AnalyticsCache:
    """Return the process-local analytics cache stored on the app."""
    cache: AnalyticsCache = request.app.state.cache
    return cache


SessionDep = Annotated[Session, Depends(get_session)]
CacheDep = Annotated["AnalyticsCache", Depends(get_cache)]
