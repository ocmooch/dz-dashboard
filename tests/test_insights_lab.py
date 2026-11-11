"""Insights Lab — insight-primitive library (analytics) + the /v1/lab endpoint.

The trust seam under test: analytics computes the *facts*, the narrator only arranges
them, and a data gap yields an *absent* insight, never a fabricated one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Season
from sqlalchemy import select

from ff_dashboard.analytics.insights import (
    draft_market_insight,
    schedule_luck_insight,
    season_insights,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


_VALID_CONFIDENCE = {"high", "medium", "low"}


def _in_progress_season_id(session: Session) -> int:
    return session.execute(
        select(Season.season_id).where(Season.status == "in_progress")
    ).scalar_one()


# --- schedule_luck primitive (reuses the xW / all-play keystone) ------------


def test_schedule_luck_primitive_voices_the_unluckiest(session: Session) -> None:
    ins = schedule_luck_insight(session, KNOWN["season_id"][2016])
    assert ins is not None
    assert ins["kind"] == "schedule_luck"
    # 2016's most-robbed is Goose — the narration must name the computed subject.
    assert ins["subject"]["owner_name"] == "Goose"
    assert ins["subject"]["owner_id"] == KNOWN["owner_id"]["goose"]
    assert "Goose" in ins["narration"]
    # Every voiced number is also an addressable fact (the narrator computes none).
    fact_labels = {f["label"] for f in ins["facts"]}
    assert {"Actual wins", "Expected (all-play) wins", "Luck gap"} <= fact_labels
    assert ins["confidence"] in _VALID_CONFIDENCE
    # Provenance traces the claim back to a real, tested view.
    assert ins["provenance"]["endpoint"].endswith("/standings/insights")


def test_schedule_luck_is_absent_for_an_unplayed_season(session: Session) -> None:
    # The seeded-but-unplayed season has no completed matchups → no luck to read.
    assert schedule_luck_insight(session, _in_progress_season_id(session)) is None


# --- draft_market primitive (reuses the recalibrated ADP axis) --------------


def test_draft_market_primitive_voices_the_biggest_reach(session: Session) -> None:
    ins = draft_market_insight(session, KNOWN["season_id"][2016])
    assert ins is not None
    assert ins["kind"] == "draft_market"
    # 2016's biggest reach is Kelce at #1 (Δ -7.4 clears its cushion).
    assert "Travis Kelce" in ins["narration"]
    assert "#1" in ins["narration"]
    fact_labels = {f["label"] for f in ins["facts"]}
    assert {"Drafted at", "Consensus ADP", "Picks ahead of market"} <= fact_labels
    # 2016 blends FFC → full coverage → high confidence, no coverage note carried.
    assert ins["confidence"] == "high"
    assert ins["_coverage_note"] is None


def test_draft_market_is_absent_without_a_captured_draft(session: Session) -> None:
    # 2015 has no captured draft → the market read can't be made.
    assert draft_market_insight(session, KNOWN["season_id"][2015]) is None


# --- season_insights builder ------------------------------------------------


def test_season_insights_collects_both_primitives(session: Session) -> None:
    out = season_insights(session, KNOWN["season_id"][2016])
    assert out["available"] is True
    assert out["season_year"] == 2016
    kinds = {i["kind"] for i in out["insights"]}
    assert {"schedule_luck", "draft_market"} <= kinds
    # 2016 is fully covered (FFC present) → no honesty notes.
    assert out["notes"] == []
    # The transient coverage carrier is stripped before serving.
    assert all("_coverage_note" not in i for i in out["insights"])


def test_season_insights_unavailable_when_nothing_fires(session: Session) -> None:
    # The unplayed season has neither completed matchups nor a draft → an honest
    # empty payload, not a fabricated insight.
    out = season_insights(session, _in_progress_season_id(session))
    assert out["available"] is False
    assert out["insights"] == []


# --- endpoint ---------------------------------------------------------------


def test_lab_insights_endpoint(client: TestClient) -> None:
    resp = client.get(f"/v1/lab/insights/{KNOWN['season_id'][2016]}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"data", "meta"}
    data = body["data"]
    assert data["available"] is True
    assert data["season_year"] == 2016
    kinds = {i["kind"] for i in data["insights"]}
    assert {"schedule_luck", "draft_market"} <= kinds
    # The serving schema drops the transient coverage carrier.
    assert all("_coverage_note" not in i for i in data["insights"])
