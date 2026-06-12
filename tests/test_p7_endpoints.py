"""P7 — team-page contract tests: envelope, values, 404, and 503."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import KNOWN

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _envelope(resp) -> dict:  # type: ignore[no-untyped-def]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["pipeline_run_id"] == KNOWN["run_id"]
    return body["data"]


# --- Overview --------------------------------------------------------------


def test_team_overview_endpoint(client: TestClient) -> None:
    tid = KNOWN["team_id"][(2017, "ice")]
    data = _envelope(client.get(f"/v1/teams/{tid}"))
    assert data["owner_name"] == "Iceman"
    assert data["rank"] == 1
    assert data["wins"] == 2
    assert data["is_champion"] is False


def test_team_overview_not_found(client: TestClient) -> None:
    resp = client.get("/v1/teams/999999")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


# --- Roster ----------------------------------------------------------------


def test_team_roster_endpoint(client: TestClient) -> None:
    tid = KNOWN["team_id"][(2017, "ice")]
    data = _envelope(client.get(f"/v1/teams/{tid}/roster?week=1"))
    assert data["week"] == 1
    assert len(data["players"]) == 13
    assert 1 in data["weeks_available"]
    dst = next(p for p in data["players"] if p["position"] == "DEF")
    assert dst["league_points"] == 9.0  # DST scored end-to-end


def test_team_roster_not_found(client: TestClient) -> None:
    resp = client.get("/v1/teams/999999/roster")
    assert resp.status_code == 404


# --- Schedule --------------------------------------------------------------


def test_team_schedule_endpoint(client: TestClient) -> None:
    tid = KNOWN["team_id"][(2017, "ice")]
    data = _envelope(client.get(f"/v1/teams/{tid}/schedule"))
    assert len(data["games"]) == 2
    assert all(g["matchup_id"] is not None for g in data["games"])
    assert {g["result"] for g in data["games"]} == {"W"}


# --- Scoring trend ---------------------------------------------------------


def test_team_scoring_trend_endpoint(client: TestClient) -> None:
    tid = KNOWN["team_id"][(2017, "ice")]
    data = _envelope(client.get(f"/v1/teams/{tid}/scoring-trend"))
    pts = {p["week"]: p for p in data["points"]}
    assert pts[1]["league_avg"] == 133.85
    assert pts[2]["league_avg"] == 113.75


# --- Transactions ----------------------------------------------------------


def test_team_transactions_endpoint(client: TestClient) -> None:
    tid = KNOWN["team_id"][(2017, "ice")]
    data = _envelope(client.get(f"/v1/teams/{tid}/transactions"))
    assert [t["transaction_type"] for t in data["transactions"]] == [
        "waiver_add",
        "lineup_change",
    ]
    assert data["transactions"][0]["waiver_priority_used"] == 4
    assert data["transactions"][0]["faab_bid"] is None
    assert data["transactions"][1]["extra_data"] == {"from_slot": "BN", "to_slot": "WR"}


# --- 503 when the pipeline never ran (empty DB) ----------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/v1/teams/1",
        "/v1/teams/1/roster",
        "/v1/teams/1/schedule",
        "/v1/teams/1/scoring-trend",
        "/v1/teams/1/transactions",
    ],
)
def test_empty_db_returns_503(empty_client: TestClient, path: str) -> None:
    resp = empty_client.get(path)
    assert resp.status_code == 503
    assert resp.json()["error"] == "service_unavailable"
