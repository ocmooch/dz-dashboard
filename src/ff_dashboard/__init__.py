"""ff_dashboard — Phase 2 analytics backend-for-frontend.

A read-only FastAPI service that reuses Phase 1's ``ff_pipeline.repository``
to read the league SQLite database and computes every derived metric
server-side. The React SPA in ``web/`` is pure presentation and talks only
to this service. See docs/ for the full design package.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dz-dashboard")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
