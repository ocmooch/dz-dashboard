"""In-process memoization for analytics rollups.

Rollups (records book, rivalry matrix, owner careers) are stable between
pipeline runs and there is a single user, so a process-local dict is the right
cache. The key always includes the latest ``pipeline_run_id`` — when Phase 1
runs again the run id changes and every prior entry is naturally bypassed, so
invalidation is free and correct.

Stored on ``app.state.cache``; tests construct their own instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from ff_pipeline.repository.queries import latest_pipeline_run

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

T = TypeVar("T")


class AnalyticsCache:
    """Memoize values keyed by ``(latest_pipeline_run_id, name)``."""

    def __init__(self) -> None:
        self._store: dict[tuple[int | None, str], Any] = {}

    def get_or_compute(self, session: Session, name: str, compute: Callable[[], T]) -> T:
        run = latest_pipeline_run(session)
        run_id = run.run_id if run is not None else None
        key = (run_id, name)
        if key in self._store:
            return self._store[key]  # type: ignore[no-any-return]
        value = compute()
        self._store[key] = value
        return value

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
