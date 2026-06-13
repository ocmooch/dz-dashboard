"""League-history product read models."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ff_dashboard.analytics.league_history import (
    _change,
    _owner_aliases,
    _resolve_setting_gaps,
    _setting_actor,
    league_eras,
    league_overview,
    league_stories,
    league_timeline,
    manager_directory,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


def _envelope(resp):  # type: ignore[no-untyped-def]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["pipeline_run_id"] == KNOWN["run_id"]
    return body["data"]


def _has_change(details: list[dict], **expected) -> bool:  # type: ignore[type-arg]
    """Return True if any change detail has all expected key-value pairs."""
    return any(all(item.get(k) == v for k, v in expected.items()) for item in details)


def test_league_overview_counts_and_caveats(session: Session) -> None:
    data = league_overview(session)
    assert data["name"] == "Danger Zone Test League"
    assert data["start_year"] == 2015
    assert data["season_count"] == 3
    assert data["completed_seasons"] == 3
    assert data["scored_seasons"] == 2
    assert data["champions_recorded"] == 3
    assert (
        data["current_era"]["label"]
        == "4-team league / 2-week regular season / reconstructed player-scoring era"
    )
    assert {c["code"] for c in data["data_caveats"]} == {
        "rules_not_fully_scraped",
        "player_scoring_by_season",
    }


def test_league_timeline_labels_scoring_provenance(session: Session) -> None:
    data = league_timeline(session)
    by_year = {row["season_year"]: row for row in data["seasons"]}
    assert by_year[2015]["is_scored"] is False
    assert by_year[2015]["league_size"] == 4
    assert by_year[2015]["verification_status"] == "known_source_gap"
    assert by_year[2015]["scoring_provenance"] == "nfl_com_authoritative_total"
    assert by_year[2016]["is_scored"] is True
    assert by_year[2016]["verification_status"] == "verification_pending"
    assert by_year[2016]["changes"]["scoring_availability_changed"] is True
    details_2016 = by_year[2016]["changes"]["details"]
    assert _has_change(
        details_2016,
        category="scoring_provenance",
        title="Scoring provenance changed",
        before="nfl com authoritative total",
        after="nflverse reconstructed",
        source="derived_from_db",
        certainty="source_limited",
    )
    assert by_year[2017]["champion"]["owner_name"] == "Maverick"


def test_league_eras_are_derived_from_material_context_changes(session: Session) -> None:
    data = league_eras(session)
    assert [era["season_years"] for era in data["eras"]] == [[2015], [2016, 2017]]
    change_2016 = next(change for change in data["changes"] if change["season_year"] == 2016)
    assert change_2016["league_size_changed"] is False
    assert change_2016["schedule_changed"] is False
    assert change_2016["scoring_availability_changed"] is True
    assert _has_change(
        change_2016["details"],
        category="scoring_provenance",
        title="Scoring provenance changed",
        before="nfl com authoritative total",
        after="nflverse reconstructed",
        source="derived_from_db",
        certainty="source_limited",
    )


def test_manager_directory_separates_identity_from_team_names(session: Session) -> None:
    data = manager_directory(session)
    mav = next(m for m in data["managers"] if m["display_name"] == "Maverick")
    assert mav["manager_id"] == KNOWN["owner_id"]["mav"]
    assert mav["active_years"] == [2015, 2016, 2017]
    assert mav["team_names"] == ["Maverick 2015", "Maverick 2016", "Maverick 2017"]
    slider = next(m for m in data["managers"] if m["display_name"] == "Slider")
    assert slider["left_year"] == 2016
    assert "Dynasty Crew" in slider["team_names"]


def test_owner_aliases_normalizes_upstream_provenance_dict() -> None:
    assert _owner_aliases({"display_names": ["Adam"], "nfl_user_ids": ["126"]}) == ["Adam"]


def test_league_stories_use_unique_matchups_and_gap_cards(session: Session) -> None:
    data = league_stories(session)
    by_id = {story["story_id"]: story for story in data["stories"]}
    assert by_id["biggest-blowout"]["metric_value"] == 70.0
    assert by_id["biggest-blowout"]["primary_team"]["owner_name"] == "Maverick"
    assert by_id["close-loss-magnet"]["metric_value"] == 1
    assert by_id["worst-beat"]["available"] is True
    assert by_id["worst-beat"]["metric_value"] == 110.0
    assert by_id["worst-beat"]["primary_team"]["owner_name"] == "Maverick"
    assert by_id["team-name-hall"]["items"] == [{"team_name": "Dynasty Crew", "seasons": 2}]


def test_league_endpoints(client: TestClient) -> None:
    overview = _envelope(client.get("/v1/league/overview"))
    assert overview["season_count"] == 3
    timeline = _envelope(client.get("/v1/league/timeline"))
    assert timeline["seasons"][0]["season_year"] == 2015
    eras = _envelope(client.get("/v1/league/eras"))
    assert len(eras["eras"]) == 2
    stories = _envelope(client.get("/v1/league/stories"))
    assert {s["story_id"] for s in stories["stories"]} >= {"biggest-blowout", "worst-beat"}
    managers = _envelope(client.get("/v1/league/managers"))
    assert len(managers["managers"]) == 5


def test_commissioner_history(session: Session) -> None:
    from ff_dashboard.analytics.commissioners import commissioner_for_year, commissioner_history

    terms = commissioner_history(session)
    assert len(terms) == 2
    names = [t.owner_name for t in terms]
    assert "Maverick" in names
    assert "Viper" in names

    mav = next(t for t in terms if t.owner_name == "Maverick")
    assert mav.from_year == 2015
    assert mav.to_year == 2016
    assert mav.seasons == 2

    viper = next(t for t in terms if t.owner_name == "Viper")
    assert viper.from_year == 2017
    assert viper.to_year is None
    assert viper.seasons >= 1

    # Year lookup helper.
    assert commissioner_for_year(terms, 2015) == mav
    assert commissioner_for_year(terms, 2016) == mav
    assert commissioner_for_year(terms, 2017) == viper
    assert commissioner_for_year(terms, 2020) == viper
    assert commissioner_for_year(terms, 2014) is None


def test_setting_actor_extracts_manager_name() -> None:
    assert _setting_actor("Chris updated roster positions") == "Chris"
    assert _setting_actor("harry updated scoring settings") == "harry"
    # Defensive fallback when the headline does not match the known shape.
    assert _setting_actor("something unexpected") == "A manager"


def _gap(category: str, title: str, summary: str) -> dict:  # type: ignore[type-arg]
    return _change(
        category,
        title,
        summary,
        source="nfl_com_transaction_log",
        description_gap=True,
    )


def test_resolve_setting_gaps_drops_redundant_headline() -> None:
    # A derived structural diff for the same category already explains the change,
    # so the vague NFL.com headline is dropped as redundant.
    derived = _change("roster_slots", "Starting lineup changed", "+1 WR/RB flex; WR: 3→2")
    headline = _gap(
        "roster_slots", "Roster positions setting updated", "Chris updated roster positions"
    )
    resolved = _resolve_setting_gaps([derived, headline], SimpleNamespace(year=2010))
    assert resolved == [derived]


def test_resolve_setting_gaps_rewrites_lone_headline_with_prior_year() -> None:
    headline = _gap("scoring_rules", "Scoring settings updated", "Dan updated scoring settings")
    [resolved] = _resolve_setting_gaps([headline], SimpleNamespace(year=2023))
    assert resolved["description_gap"] is False
    assert resolved["certainty"] == "source_limited"
    assert resolved["summary"].startswith("Dan edited scoring settings on NFL.com")
    assert "unchanged from 2023" in resolved["summary"]
    assert "scoring rules tracked here are unchanged" in resolved["summary"]


def test_resolve_setting_gaps_rewrites_roster_headline_without_prior_season() -> None:
    headline = _gap(
        "roster_slots", "Roster positions setting updated", "Chris updated roster positions"
    )
    [resolved] = _resolve_setting_gaps([headline], None)
    assert resolved["description_gap"] is False
    # No prior season to compare against, so no "unchanged from <year>" claim is made.
    assert "unchanged from" not in resolved["summary"]
    assert resolved["summary"].startswith("Chris edited roster settings on NFL.com")


def test_commissioner_in_league_overview_endpoint(client: TestClient) -> None:
    overview = _envelope(client.get("/v1/league/overview"))
    commissioners = overview["commissioners"]
    assert isinstance(commissioners, list)
    assert len(commissioners) == 2
    assert commissioners[0]["owner_name"] == "Maverick"
    assert commissioners[0]["from_year"] == 2015
    assert commissioners[0]["to_year"] == 2016
    assert commissioners[1]["owner_name"] == "Viper"
    assert commissioners[1]["to_year"] is None
