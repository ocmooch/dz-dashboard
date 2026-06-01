"""FastAPI application factory for the dashboard BFF.

Mirrors ``ff_pipeline.api.main.create_app``: routes live in modules under
``routes/`` and the factory wires them up. A pre-built engine/cache can be
injected so integration tests bind a temp-file SQLite database without
monkey-patching (the production CLI leaves both ``None`` and derives them from
``Settings``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ff_pipeline.api.errors import install_error_handlers

from ff_dashboard.api.routes import (
    draft,
    health,
    matchups,
    owners,
    players,
    power,
    records,
    search,
    seasons,
    teams,
)
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine

API_TITLE = "dz-dashboard analytics API"
API_VERSION = "v1"


def create_app(
    engine: Engine | None = None,
    *,
    cache: AnalyticsCache | None = None,
    cors_origins: list[str] | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build the FastAPI app, optionally bound to a custom engine/cache.

    ``static_dir`` (or the ``DASHBOARD_STATIC_DIR`` setting in the CLI path) makes
    the app also serve a built SPA single-origin; left ``None`` it is API-only.
    """
    if engine is None:
        from ff_dashboard.settings import get_settings

        settings = get_settings()
        engine = create_readonly_engine(settings.resolved_database_url())
        if cors_origins is None:
            cors_origins = settings.cors_origins
        if static_dir is None:
            static_dir = settings.resolved_static_dir()

    app = FastAPI(title=API_TITLE, version=API_VERSION)
    app.state.engine = engine
    app.state.cache = cache if cache is not None else AnalyticsCache()

    install_error_handlers(app)

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(seasons.router)
    app.include_router(owners.router)
    app.include_router(records.router)
    app.include_router(players.router)
    app.include_router(matchups.router)
    app.include_router(draft.router)
    app.include_router(power.router)
    app.include_router(teams.router)
    app.include_router(search.router)

    # Single-origin SPA serving (production-ish local run). Mounted last so the
    # API routers above always win; off unless DASHBOARD_STATIC_DIR points at a
    # built web/dist. Skipped silently if the directory isn't built yet.
    if static_dir is not None and (static_dir / "index.html").is_file():
        from ff_dashboard.api.static import mount_spa

        mount_spa(app, static_dir)

    return app
