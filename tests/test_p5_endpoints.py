"""P5 — matchups & box-score contract tests: envelope, gaps, 404, 503."""

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


# --- Week matchups ---------------------------------------------------------


def test_week_matchups_endpoint(client: TestClient) -> None:
    sid = KNOWN["season_id"][2017]
    data = _envelope(client.get(f"/v1/seasons/{sid}/weeks/1/matchups"))
    assert data["week"] == 1
    assert data["is_scored"] is True
    assert len(data["games"]) == 2  # deduped from four perspective rows
    assert all(g["matchup_id"] is not None for g in data["games"])


def test_week_matchups_season_not_found(client: TestClient) -> None:
    resp = client.get("/v1/seasons/99999/weeks/1/matchups")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


# --- Box score -------------------------------------------------------------


def test_box_score_endpoint_envelope_and_values(client: TestClient) -> None:
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = _envelope(client.get(f"/v1/matchups/{mid}/box-score"))
    assert data["available"] is True
    home = data["home"]
    assert home["starter_points"] == 113.0  # includes the 9.0 DST
    assert home["optimal_total"] == 126.0
    assert home["points_left_on_bench"] == 13.0
    assert home["bench_points"] == 51.0
    assert data["winner_team_id"] == KNOWN["team_id"][(2017, "ice")]


def test_box_score_dst_is_scored(client: TestClient) -> None:
    mid = KNOWN["matchup_id"][(2017, 1, "ice")]
    data = _envelope(client.get(f"/v1/matchups/{mid}/box-score"))
    dst = next(p for p in data["home"]["lineup"] if p["position"] == "DEF")
    assert dst["league_points"] == 9.0  # DST scored end-to-end, not a gap
    assert dst["available"] is True
    assert dst["reason"] is None


def test_box_score_pre_2016_gap(client: TestClient) -> None:
    mid = KNOWN["matchup_id"][(2015, 1, "mav")]
    data = _envelope(client.get(f"/v1/matchups/{mid}/box-score"))
    assert data["available"] is False
    assert data["reason"] == "season_unscored"
    assert data["home"] is None


def test_box_score_not_found(client: TestClient) -> None:
    resp = client.get("/v1/matchups/99999/box-score")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


# --- 503 when the pipeline never ran (empty DB) ----------------------------


@pytest.mark.parametrize("path", ["/v1/seasons/1/weeks/1/matchups", "/v1/matchups/1/box-score"])
def test_empty_db_returns_503(empty_client: TestClient, path: str) -> None:
    resp = empty_client.get(path)
    assert resp.status_code == 503
    assert resp.json()["error"] == "service_unavailable"
