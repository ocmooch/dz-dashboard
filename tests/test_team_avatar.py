"""Q11 — team-avatar route.

Streams a team's season logo from the on-disk asset store, and 404s (never
errors, never 500s) on every missing/invalid case so the SPA falls back to its
monogram chip. Owner avatars are intentionally not served (no source rows).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from tests.conftest import AVATAR_PNG, KNOWN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy import Engine


@pytest.fixture
def avatar_client(engine: Engine, fixture_assets_root: Path) -> Iterator[TestClient]:
    """A client whose app is bound to the fixture's on-disk asset store."""
    app = create_app(
        engine, cache=AnalyticsCache(), cors_origins=[], assets_root=fixture_assets_root
    )
    with TestClient(app) as c:
        yield c


def _team(year: int, key: str) -> int:
    return int(KNOWN["team_id"][(year, key)])


def test_serves_team_logo_bytes(avatar_client: TestClient) -> None:
    resp = avatar_client.get(f"/v1/teams/{_team(2017, 'mav')}/avatar")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == AVATAR_PNG
    assert "immutable" in resp.headers.get("cache-control", "")


def test_team_without_avatar_is_404(avatar_client: TestClient) -> None:
    # Viper 2017 has a null team_avatar_asset_id → monogram fallback.
    resp = avatar_client.get(f"/v1/teams/{_team(2017, 'viper')}/avatar")
    assert resp.status_code == 404


def test_unknown_team_is_404(avatar_client: TestClient) -> None:
    resp = avatar_client.get("/v1/teams/999999/avatar")
    assert resp.status_code == 404


def test_missing_file_on_disk_is_404(avatar_client: TestClient) -> None:
    # Iceman 2017 points at an asset row whose bytes were never written.
    resp = avatar_client.get(f"/v1/teams/{_team(2017, 'ice')}/avatar")
    assert resp.status_code == 404


def test_path_traversal_is_rejected(avatar_client: TestClient) -> None:
    # Goose 2017 points at an asset whose storage_path escapes the store.
    resp = avatar_client.get(f"/v1/teams/{_team(2017, 'goose')}/avatar")
    assert resp.status_code == 404


def test_unconfigured_store_is_404(client: TestClient) -> None:
    # The default client has no assets_root bound → route 404s gracefully.
    resp = client.get(f"/v1/teams/{_team(2017, 'mav')}/avatar")
    assert resp.status_code == 404
