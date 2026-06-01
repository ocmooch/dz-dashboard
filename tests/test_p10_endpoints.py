"""P10 — search endpoint contract tests: envelope, values, and validation.

Search is intentionally always-available navigation (no 503 gap): a no-match
query returns an empty hit list with a 200, never a fabricated error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import KNOWN

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _envelope(resp) -> dict:  # type: ignore[no-untyped-def]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["pipeline_run_id"] == KNOWN["run_id"]
    return body["data"]


def test_search_owner(client: TestClient) -> None:
    data = _envelope(client.get("/v1/search", params={"q": "Mav"}))
    assert data["query"] == "Mav"
    assert "Maverick" in {h["label"] for h in data["hits"]}


def test_search_player(client: TestClient) -> None:
    data = _envelope(client.get("/v1/search", params={"q": "McCaffrey"}))
    hit = next(h for h in data["hits"] if h["type"] == "player")
    assert hit["label"] == "Christian McCaffrey"
    assert hit["href"] == f"/players/{KNOWN['player_id']['cmc']}"


def test_search_season(client: TestClient) -> None:
    data = _envelope(client.get("/v1/search", params={"q": "2017"}))
    assert any(h["label"] == "2017 season" and h["href"] == "/standings" for h in data["hits"])


def test_search_no_match_is_empty_not_error(client: TestClient) -> None:
    assert _envelope(client.get("/v1/search", params={"q": "zzzznope"}))["hits"] == []


def test_search_blank_query_rejected(client: TestClient) -> None:
    # q has min_length=1; an empty string is a validation error, which the app's
    # error handler renders as a 400 (not FastAPI's default 422).
    resp = client.get("/v1/search", params={"q": ""})
    assert resp.status_code == 400
    assert resp.json()["error"] == "bad_request"


def test_search_limit(client: TestClient) -> None:
    data = _envelope(client.get("/v1/search", params={"q": "Ice", "limit": 1}))
    assert len(data["hits"]) <= 1
