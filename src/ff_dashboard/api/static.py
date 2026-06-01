"""Optional single-origin SPA serving for the production-ish local run.

In development the Vite dev server serves ``web/`` and proxies the API to the
BFF (two processes). For daily use it is simpler to run *one* process: this
module mounts a built ``web/dist`` so the same uvicorn that serves ``/v1`` also
serves the SPA shell and its assets — no second server, no CORS.

It is mounted only when ``DASHBOARD_STATIC_DIR`` is set (see ``settings.py``);
tests and the default dev flow leave it off, so API-only behaviour (e.g. JSON
``404`` envelopes for unknown ``/v1`` routes) is unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from ff_pipeline.api.errors import not_found

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI
    from starlette.responses import Response

# Path prefixes owned by the API/docs. A request under one of these that the
# routers did not match is a genuine 404 — never the SPA shell — so API clients
# keep getting JSON errors instead of an HTML page.
_RESERVED_PREFIXES = ("v1/", "health", "openapi.json", "docs", "redoc")


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA from ``static_dir`` on the same app.

    Hashed assets are served from ``/assets``; every other unmatched GET returns
    ``index.html`` so client-side routes (deep links like ``/standings``) resolve.
    Call this *after* the API routers are included so explicit routes win.
    """
    index = static_dir / "index.html"
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> Response:
        if full_path.startswith(_RESERVED_PREFIXES):
            # An unmatched API/doc path: keep the JSON 404 envelope.
            raise not_found(f"No route for /{full_path}")
        # A real top-level file (favicon.ico, robots.txt, …) is served directly;
        # everything else falls back to the SPA shell for client-side routing.
        candidate = (static_dir / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(static_dir.resolve())
        ):
            return FileResponse(candidate)
        return FileResponse(index)
