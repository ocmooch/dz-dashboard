"""P11 — single-origin SPA serving (production-ish local run).

When ``DASHBOARD_STATIC_DIR`` / ``create_app(static_dir=...)`` points at a built
``web/dist``, the same app serves the SPA shell and assets without disturbing
the API: ``/v1`` routes, ``/health`` and ``/openapi.json`` still answer, and an
unknown ``/v1`` path still returns the JSON 404 envelope (never the HTML shell).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine

INDEX_HTML = "<!doctype html><title>Danger Zone</title><div id=root></div>"


@pytest.fixture
def static_client(engine: Engine, tmp_path: Path) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export const x = 1;", encoding="utf-8")
    (dist / "favicon.ico").write_bytes(b"\x00")
    app = create_app(engine, cache=AnalyticsCache(), cors_origins=[], static_dir=dist)
    return TestClient(app)


def test_serves_spa_shell_at_root(static_client: TestClient) -> None:
    resp = static_client.get("/")
    assert resp.status_code == 200
    assert "id=root" in resp.text


def test_deep_link_falls_back_to_shell(static_client: TestClient) -> None:
    # A client-side route that has no file on disk must still load the SPA.
    resp = static_client.get("/standings")
    assert resp.status_code == 200
    assert "id=root" in resp.text


def test_serves_hashed_assets(static_client: TestClient) -> None:
    resp = static_client.get("/assets/app.js")
    assert resp.status_code == 200
    assert "export const x" in resp.text


def test_serves_real_top_level_file(static_client: TestClient) -> None:
    resp = static_client.get("/favicon.ico")
    assert resp.status_code == 200


def test_api_routes_still_win(static_client: TestClient) -> None:
    assert static_client.get("/health").json() == {"status": "ok"}
    assert static_client.get("/v1/meta").status_code == 200
    assert static_client.get("/openapi.json").status_code == 200


def test_unknown_api_path_keeps_json_404(static_client: TestClient) -> None:
    # Crucially NOT the SPA shell — API clients keep getting JSON errors.
    resp = static_client.get("/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"
    assert "id=root" not in resp.text


def test_api_only_by_default(client: TestClient) -> None:
    # No static_dir: the catch-all SPA route is absent, so a non-API path 404s.
    resp = client.get("/standings")
    assert resp.status_code == 404
