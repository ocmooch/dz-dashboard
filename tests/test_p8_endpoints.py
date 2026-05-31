"""P8 — draft contract tests: envelopes, steals/busts, gap behaviour, 404/503."""

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


def test_draft_board_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/draft"))
    assert data["available"] is True
    assert data["num_teams"] == 4
    picks = data["rounds"][0]["picks"]
    assert [p["player_name"] for p in picks][-1] == "Christian McCaffrey"
    assert picks[-1]["value"] == KNOWN["draft_top_steal"]["value"]


def test_draft_board_gap_is_200_not_404(client: TestClient) -> None:
    # An uncaptured draft is an honest 200 gap payload, never a 404 or fake zeros.
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2015]}/draft"))
    assert data["available"] is False
    assert data["reason"] == "draft_not_captured"
    assert data["rounds"] == []


def test_draft_value_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/draft/value"))
    assert data["steals"][0]["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert data["busts"][0]["player_name"] == KNOWN["draft_top_bust"]["player"]
    assert data["slot_window"] == 2
    assert data["definition"]


def test_draft_records_endpoint(client: TestClient) -> None:
    data = _envelope(client.get("/v1/records/draft"))
    assert data["available"] is True
    assert data["best_picks"][0]["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert data["worst_picks"][0]["player_name"] == KNOWN["draft_top_bust"]["player"]


def test_draft_board_unknown_season_404(client: TestClient) -> None:
    assert client.get("/v1/seasons/99999/draft").status_code == 404
    assert client.get("/v1/seasons/99999/draft/value").status_code == 404


def test_draft_503_when_pipeline_never_ran(empty_client: TestClient) -> None:
    assert empty_client.get("/v1/seasons/1/draft").status_code == 503
