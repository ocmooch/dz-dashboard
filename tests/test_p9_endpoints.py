"""P9 — power-ranking contract tests: envelopes, explainer, timeline, 404."""

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


def test_power_ranking_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/power"))
    assert data["through_week"] == 2
    assert data["explainer"]
    assert round(sum(data["weights"].values()), 6) == 1.0
    rows = data["rows"]
    assert [r["rank"] for r in rows] == [1, 2, 3, 4]
    top = rows[0]
    assert top["owner_name"] == "Maverick"
    assert top["power_score"] == KNOWN["power_2016"]["mav"]["power_score"]
    assert top["rank_delta"] == 0


def test_power_through_week_query(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/power?through_week=1"))
    assert data["through_week"] == 1


def test_power_timeline_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/power/timeline"))
    assert data["regular_season_weeks"] == 2
    assert len(data["teams"]) == 4
    for team in data["teams"]:
        assert [p["week"] for p in team["points"]] == [1, 2]


def test_power_unknown_season_404(client: TestClient) -> None:
    assert client.get("/v1/seasons/99999/power").status_code == 404
    assert client.get("/v1/seasons/99999/power/timeline").status_code == 404
