"""League-history product read models."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from ff_dashboard.analytics.league_history import (
    _assign_era_ids,
    _era_defining_change,
    _flex_label,
    _owner_aliases,
    _ppr_label,
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
    # Eras are now playstyle spans; the fixture shares one playstyle across all seasons.
    assert data["current_era"]["season_years"] == [2015, 2016, 2017]
    assert data["current_era"]["lineup"] == "No flex"
    assert data["current_era"]["defining_change"] == "Earliest recorded ruleset"
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
    # era_id tags each season with its playstyle era, matching league_eras(). The
    # fixture's playstyle is constant, so all seasons share one era (a scoring-
    # provenance change is bookkeeping, not playstyle, and no longer splits eras).
    assert by_year[2015]["era_id"] == "era-1"
    assert by_year[2016]["era_id"] == "era-1"
    assert by_year[2017]["era_id"] == "era-1"


def test_league_eras_are_derived_from_material_context_changes(session: Session) -> None:
    data = league_eras(session)
    assert [era["season_years"] for era in data["eras"]] == [[2015, 2016, 2017]]
    assert [era["era_id"] for era in data["eras"]] == ["era-1"]
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


# --- playstyle era logic (synthetic, fixture-independent) -------------------
def test_ppr_label_classifies_reception_value() -> None:
    assert _ppr_label(1.0) == "Full PPR"
    assert _ppr_label(0.5) == "Half PPR"
    assert _ppr_label(0.0) == "Non-PPR"
    assert _ppr_label(None) is None


def test_flex_label_reads_the_salient_lineup_trait() -> None:
    assert _flex_label(Counter({"QB": 1, "R/W/T": 1})) == "RB/WR/TE flex"
    assert _flex_label(Counter({"QB": 1, "W/R": 1})) == "WR/RB flex"
    assert _flex_label(Counter({"QB": 1, "WR": 3})) == "No flex"
    assert _flex_label(Counter()) is None


def _era_row(year: int, *, ppr: float | None, flex: str | None, waiver: str | None) -> dict:  # type: ignore[type-arg]
    return {
        "season_year": year,
        "ppr_reception_value": ppr,
        "lineup_flex": flex,
        "waiver_system": waiver,
    }


def test_eras_split_on_highly_significant_playstyle_changes() -> None:
    # PPR doubles, then a flex change, then a move to FAAB -> four eras.
    rows = [
        _era_row(2010, ppr=0.5, flex="No flex", waiver="Standings-order waivers"),
        _era_row(2011, ppr=1.0, flex="WR/RB flex", waiver="Standings-order waivers"),
        _era_row(2012, ppr=1.0, flex="WR/RB flex", waiver="Standings-order waivers"),
        _era_row(2016, ppr=1.0, flex="RB/WR/TE flex", waiver="Standings-order waivers"),
        _era_row(2021, ppr=1.0, flex="RB/WR/TE flex", waiver="FAAB budget"),
    ]
    _assign_era_ids(rows)
    assert [r["era_id"] for r in rows] == ["era-1", "era-2", "era-2", "era-3", "era-4"]


def test_era_defining_change_names_only_what_shifted() -> None:
    e1 = _era_row(2010, ppr=0.5, flex="No flex", waiver="Standings-order waivers")
    e2 = _era_row(2011, ppr=1.0, flex="WR/RB flex", waiver="Standings-order waivers")
    e3 = _era_row(2021, ppr=1.0, flex="WR/RB flex", waiver="FAAB budget")
    assert _era_defining_change(e1, None) == "Earliest recorded ruleset"
    assert _era_defining_change(e2, e1) == "Full PPR scoring; WR/RB flex"
    assert _era_defining_change(e3, e2) == "FAAB budget"


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
    assert len(eras["eras"]) == 1
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


def _setting_events(details: list[dict]) -> list[dict]:  # type: ignore[type-arg]
    return [d for d in details if d.get("source") == "nfl_com_transaction_log"]


def test_timeline_classifies_2016_setting_changes(session: Session) -> None:
    data = league_timeline(session)
    row = next(r for r in data["seasons"] if r["season_year"] == 2016)
    events = _setting_events(row["changes"]["details"])
    by_label = {e["human_label"]: e for e in events}

    # Division cluster -> one T2 realignment event (notable, not major) with all 3 rows.
    div = by_label["Division realignment"]
    assert div["tier"] == "T2"
    assert len(div["members"]) == 3
    assert "3 teams" in div["summary"]

    # Individual PASS (entry fee): T2 with before/after preserved.
    fee = by_label["Entry fee"]
    assert fee["tier"] == "T2"
    assert (fee["before"], fee["after"]) == ("100.00", "125.00")

    # In-season marker on the post-kickoff tiebreaker change.
    assert by_label["Tiebreaker"]["phase"] == "in_season"

    # The unrecoverable "Playoff field" headline is now folded into the routine
    # bucket rather than shown as a standalone notable row.
    assert "Playoff field" not in by_label

    # Routine bucket collapses the T3 rows, expandable to every underlying entry;
    # the headline-only scoring edit (no state diff this season) is hedged, not dropped,
    # and the demoted playoff-field row now lives here too.
    bucket = by_label["Routine changes"]
    assert bucket["tier"] == "T3"
    member_types = {m["canonical_type"] for m in bucket["members"]}
    assert {"draft_time", "scoring_settings", "playoff_teams"} <= member_types
    scoring_member = next(m for m in bucket["members"] if m["canonical_type"] == "scoring_settings")
    assert scoring_member["missing_context"] is True


def test_timeline_setting_changes_drop_nothing(session: Session) -> None:
    data = league_timeline(session)
    row = next(r for r in data["seasons"] if r["season_year"] == 2016)
    events = _setting_events(row["changes"]["details"])
    leaves = sum(len(e["members"]) if e["members"] else 1 for e in events)
    assert leaves == 8  # every seeded 2016 setting_change row is represented


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
