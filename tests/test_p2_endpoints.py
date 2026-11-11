"""P2 — contract tests: every endpoint's envelope, gaps, 404s, and 503-on-empty."""

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


# --- Seasons & standings ---------------------------------------------------


def test_list_seasons(client: TestClient) -> None:
    data = _envelope(client.get("/v1/seasons"))
    years = {s["season_year"]: s for s in data["seasons"]}
    # The upcoming, not-yet-played 2018 season (seeded with teams but no games)
    # is withheld — it has no results to show. It reappears once games land.
    assert set(years) == {2015, 2016, 2017}
    assert 2018 not in years
    assert years[2015]["is_scored"] is False
    assert years[2016]["is_scored"] is True
    assert years[2016]["champion"]["owner_name"] == "Maverick"


def test_season_summary(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2017]}"))
    assert data["season_year"] == 2017
    assert data["champion"]["owner_name"] == "Maverick"  # champ != #1 seed (Iceman)


def test_standings_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/standings"))
    assert data["rows"][0]["owner_name"] == "Maverick"
    assert data["rows"][0]["points_for"] == 270.0
    assert data["tiebreak_caveat"] is True


def test_standings_timeline_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/standings/timeline"))
    assert data["regular_season_weeks"] == 2
    a_team = data["teams"][0]
    assert len(a_team["points"]) == 2  # one point per regular-season week


def test_standings_insights_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/standings/insights"))
    assert data["available"] is True
    by_owner = {row["owner_name"]: row for row in data["teams"]}
    assert by_owner["Goose"]["all_play_win_pct"] == 0.6667
    assert by_owner["Goose"]["luck_delta"] == -0.33
    assert by_owner["Slider"]["luck_delta"] == 0.33
    # The voiced "Robbed & Blessed" picks ride the same envelope.
    assert data["most_robbed"]["owner_name"] == "Goose"
    assert data["most_blessed"]["owner_name"] == "Slider"


def test_bracket_endpoint(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2015]}/bracket"))
    assert data["available"] is True
    assert data["reason"] is None
    assert data["consolation_distinguished"] is True
    pb = data["playoff_bracket"]
    assert pb is not None
    assert len(pb["rounds"]) == 1
    assert len(pb["rounds"][0]["games"]) == 1
    assert pb["rounds"][0]["games"][0]["is_consolation"] is False
    cb = data["consolation_bracket"]
    assert cb is not None
    assert len(cb["rounds"][0]["games"]) == 1
    assert cb["rounds"][0]["games"][0]["is_consolation"] is True


def test_bracket_endpoint_gap(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/bracket"))
    assert data["available"] is False
    assert data["reason"] == "bracket_unavailable"
    assert data["playoff_bracket"] is None
    assert data["consolation_bracket"] is None


def test_conferences_endpoint_reports_real_season_year(client: TestClient) -> None:
    # Regression: when the conference-aware ff_pipeline models aren't present the
    # endpoint must still return the real season_year (an int) with
    # available=False — not a None year, which 500s the int-typed schema.
    data = _envelope(client.get(f"/v1/seasons/{KNOWN['season_id'][2017]}/conferences"))
    assert data["season_year"] == 2017
    assert isinstance(data["available"], bool)


def test_conferences_endpoint_accepts_week_and_reports_mapping_gap(client: TestClient) -> None:
    data = _envelope(
        client.get(f"/v1/seasons/{KNOWN['season_id'][2017]}/conferences?through_week=1")
    )
    assert data["through_week"] == 1
    assert data["regular_season_weeks"] == 2
    assert data["available"] is False
    assert data["reason"] == "historical_division_mapping_gap"
    assert data["mapping_issues"]


def test_conferences_not_found(client: TestClient) -> None:
    resp = client.get("/v1/seasons/99999/conferences")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_season_not_found(client: TestClient) -> None:
    resp = client.get("/v1/seasons/99999/standings")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"
    resp = client.get("/v1/seasons/99999/bracket")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


# --- Owners ----------------------------------------------------------------


def test_list_owners(client: TestClient) -> None:
    data = _envelope(client.get("/v1/owners"))
    assert data["owners"][0]["display_name"] == "Maverick"
    assert data["owners"][0]["championships"] == 2


def test_owner_career(client: TestClient) -> None:
    data = _envelope(client.get(f"/v1/owners/{KNOWN['owner_id']['mav']}"))
    assert data["championships"] == 2
    assert any(t["is_champion"] for t in data["trophy_case"])
    assert data["consistency"]["available"] is True
    assert data["consistency"]["signature"] in {
        "balanced scorer",
        "ceiling scorer",
        "floor risk",
        "steady scorer",
        "true boom/bust",
        "uphill scorer",
        "volatile scorer",
        "weekly edge",
    }
    assert data["consistency"]["weeks_sampled"] > 0
    assert 0 <= data["consistency"]["top_week_rate"] <= 1
    assert 0 <= data["consistency"]["floor_week_rate"] <= 1
    assert 0 <= data["consistency"]["above_median_rate"] <= 1


def test_owner_seasons_and_trajectory(client: TestClient) -> None:
    oid = KNOWN["owner_id"]["mav"]
    seasons = _envelope(client.get(f"/v1/owners/{oid}/seasons"))
    assert len(seasons["seasons"]) == 3
    traj = _envelope(client.get(f"/v1/owners/{oid}/trajectory"))
    assert len(traj["points"]) == 3


def test_owner_story_endpoint(client: TestClient) -> None:
    oid = KNOWN["owner_id"]["mav"]
    data = _envelope(client.get(f"/v1/owners/{oid}/story"))
    assert data["available"] is True
    assert data["signature_win"]["margin"] == 70.0
    assert data["favorite_victim"]["opponent"]["owner_id"] == KNOWN["owner_id"]["ice"]
    # Gated-out superlatives are absent (null), never a fabricated value.
    assert data["nemesis"] is None
    assert data["unluckiest_season"] is None


def test_owner_story_not_found(client: TestClient) -> None:
    assert client.get("/v1/owners/99999/story").status_code == 404


def test_head_to_head_endpoint(client: TestClient) -> None:
    a, b = KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"]
    data = _envelope(client.get(f"/v1/owners/{a}/head-to-head/{b}"))
    assert data["available"] is True
    assert data["games_played"] == 3
    assert data["a_wins"] == 2


def test_head_to_head_no_meetings_is_gap_not_error(client: TestClient) -> None:
    # Slider (2015-16) and Viper (2017) never overlapped -> never met.
    a, b = KNOWN["owner_id"]["slider"], KNOWN["owner_id"]["viper"]
    data = _envelope(client.get(f"/v1/owners/{a}/head-to-head/{b}"))
    assert data["available"] is False
    assert data["reason"] == "no_meetings"
    assert data["games_played"] == 0


def test_rivalry_matrix_endpoint(client: TestClient) -> None:
    data = _envelope(client.get("/v1/owners/rivalry-matrix"))
    assert len(data["owners"]) == 5
    assert len(data["cells"]) == 25  # 5x5
    # Each owner carries an active flag so the grid can hide departed managers.
    assert all(isinstance(o["is_active"], bool) for o in data["owners"])


def test_owner_not_found(client: TestClient) -> None:
    assert client.get("/v1/owners/99999").status_code == 404


# --- Records ---------------------------------------------------------------


def test_records_endpoint(client: TestClient) -> None:
    data = _envelope(client.get("/v1/records"))
    assert data["highest_team_score"]["value"] == 160.4
    assert data["most_championships"]["owner_name"] == "Maverick"
    # The records book carries the closest-rivalry stat for its deep-linked card.
    # The small fixture has no 4+ game series, so it honestly reports the gap
    # rather than crowning a thin or lopsided pair.
    assert data["closest_rivalry"]["available"] is False


def test_championships_endpoint(client: TestClient) -> None:
    data = _envelope(client.get("/v1/records/championships"))
    by_year = {e["season_year"]: e for e in data["seasons"]}
    assert by_year[2016]["champion"]["owner_name"] == "Maverick"


# --- Players & stats -------------------------------------------------------


def test_player_index_and_detail(client: TestClient) -> None:
    # McCaffrey is rostered (Maverick, 2016-17), so he shows in the default
    # league-scoped index, enriched with his rostered span.
    idx = _envelope(client.get("/v1/players?name=McCaffrey"))
    row = idx["players"][0]
    assert row["name_full"] == "Christian McCaffrey"
    assert row["first_rostered_season"] == 2016
    assert row["last_rostered_season"] == 2017
    assert "has_scored" not in row
    detail = _envelope(client.get(f"/v1/players/{row['player_id']}"))
    assert detail["position"] == "RB"


def test_player_index_excludes_never_rostered_players(client: TestClient) -> None:
    # Jefferson is scored but never rostered in the fixture (the "nflverse
    # universe but not on a league roster" case): hidden from the public index.
    league = _envelope(client.get("/v1/players?name=Jefferson"))
    assert league["players"] == []


def test_player_scoring_gap_endpoint(client: TestClient) -> None:
    pid = KNOWN["player_id"]["lamar"]
    data = _envelope(client.get(f"/v1/players/{pid}/scoring?season=2015"))
    assert data["available"] is False
    assert data["reason"] == "season_unscored"


def test_player_availability_gap_endpoint(client: TestClient) -> None:
    pid = KNOWN["player_id"]["jjet"]
    data = _envelope(client.get(f"/v1/players/{pid}/availability?season=2016"))
    assert data["available"] is False


def test_player_insights_endpoint(client: TestClient) -> None:
    pid = KNOWN["player_id"]["cmc"]
    data = _envelope(client.get(f"/v1/players/{pid}/insights"))
    assert data["available"] is True
    assert data["best_week"]["points"] == 30.0
    assert data["best_season"]["season_year"] == 2016
    assert data["league_roster_span"]["first_rostered_season"] == 2016
    assert data["most_rostered_by"]["display_name"] == "Maverick"


def test_top_scorers_and_season_totals(client: TestClient) -> None:
    top = _envelope(client.get("/v1/stats/top-scorers?season=2016"))
    assert top["scorers"][0]["points"] == 30.0  # McCaffrey wk1
    # Jefferson's 58.0 is the top scored line but he is never rostered; the
    # rostered-ever leaderboard is led by McCaffrey (42.0, weeks 1-2).
    totals = _envelope(client.get("/v1/stats/season-totals?season=2017"))
    assert totals["totals"][0]["total_points"] == 42.0  # McCaffrey


def test_player_not_found(client: TestClient) -> None:
    assert client.get("/v1/players/99999").status_code == 404


# --- 503 when the pipeline never ran (empty DB) ----------------------------


@pytest.mark.parametrize("path", ["/v1/seasons", "/v1/owners", "/v1/owners/rivalry-matrix"])
def test_empty_db_returns_503(empty_client: TestClient, path: str) -> None:
    resp = empty_client.get(path)
    assert resp.status_code == 503
    assert resp.json()["error"] == "service_unavailable"
