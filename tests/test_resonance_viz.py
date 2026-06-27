"""Resonance-leg viz analytics: per-team weekly scores (beeswarm / intensity)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.efficiency import season_efficiency
from ff_dashboard.analytics.weekly_scores import weekly_scores
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


def test_weekly_scores_2016_known(session: Session) -> None:
    data = weekly_scores(session, KNOWN["season_id"][2016])
    assert data is not None
    assert data["available"] is True
    assert data["regular_season_weeks"] == 2
    assert len(data["teams"]) == 4
    by_team = {t["team_id"]: t for t in data["teams"]}
    mav = by_team[KNOWN["team_id"][(2016, "mav")]]
    assert [(s["week"], s["score"]) for s in mav["scores"]] == [(1, 150.0), (2, 120.0)]
    ice = by_team[KNOWN["team_id"][(2016, "ice")]]
    assert [(s["week"], s["score"]) for s in ice["scores"]] == [(1, 80.0), (2, 90.0)]
    assert all(s["is_playoff"] is False for t in data["teams"] for s in t["scores"])


def test_weekly_scores_missing_season_is_none(session: Session) -> None:
    assert weekly_scores(session, 99999) is None


def test_weekly_scores_endpoint(client: TestClient) -> None:
    resp = client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/weekly-scores")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["available"] is True
    owners = {t["owner_name"] for t in body["teams"]}
    assert {"Maverick", "Iceman", "Goose", "Slider"} <= owners


def test_season_efficiency_matches_the_hand_solved_box(session: Session) -> None:
    # Iceman 2017 wk1 is the hand-authored solvable lineup: started 113.0 of an
    # optimal 126.0 (the only week with a full lineup), so efficiency = 113/126.
    data = season_efficiency(session, KNOWN["season_id"][2017])
    assert data is not None and data["available"] is True
    by_team = {t["team_id"]: t for t in data["teams"]}
    ice = by_team[KNOWN["team_id"][(2017, "ice")]]
    assert ice["captured"] == KNOWN["box_starter_total"]  # 113.0
    assert ice["optimal"] == KNOWN["box_optimal_total"]  # 126.0
    assert ice["efficiency_pct"] == round(113.0 / 126.0, 4)
    assert ice["weeks"] == 1


def test_season_efficiency_missing_season_is_none(session: Session) -> None:
    assert season_efficiency(session, 99999) is None


def test_efficiency_endpoint(client: TestClient) -> None:
    resp = client.get(f"/v1/seasons/{KNOWN['season_id'][2017]}/efficiency")
    assert resp.status_code == 200
    assert resp.json()["data"]["available"] is True
