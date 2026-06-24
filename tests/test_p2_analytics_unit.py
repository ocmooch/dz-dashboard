"""P2 — analytics unit tests against the fixture's hand-computed known answers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Season
from sqlalchemy import select

from ff_dashboard.analytics.bracket import (
    _connected_components,
    _order_components,
    postseason_classification,
    season_bracket,
)
from ff_dashboard.analytics.head_to_head import pairwise_record, rivalry_matrix
from ff_dashboard.analytics.historical_team_names import HISTORICAL_TEAM_NAMES
from ff_dashboard.analytics.owners import list_owners_career, owner_career
from ff_dashboard.analytics.players import (
    availability,
    list_player_index,
    ownership_timeline,
    player_scoring,
)
from ff_dashboard.analytics.records import championships, records_book
from ff_dashboard.analytics.standings import compute_standings, standings_insights
from tests.conftest import KNOWN

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.orm import Session


# --- Standings -------------------------------------------------------------


def test_standings_2016_order_and_values(session: Session) -> None:
    data = compute_standings(session, KNOWN["season_id"][2016])
    assert data is not None
    got = [
        (r["owner_name"], r["wins"], r["losses"], r["ties"], r["points_for"]) for r in data["rows"]
    ]
    expected = [
        ("Maverick", 2, 0, 0, 270.0),
        ("Goose", 1, 1, 0, 210.5),  # ahead of Slider on points-for tiebreak
        ("Slider", 1, 1, 0, 194.5),
        ("Iceman", 0, 2, 0, 170.0),
    ]
    assert got == expected
    assert [r["rank"] for r in data["rows"]] == [1, 2, 3, 4]


def test_standings_basis_and_tiebreak_caveat(session: Session) -> None:
    # Fixture teams carry no final_rank, so ordering is computed; 2016 < 2019,
    # so the historical-tiebreak caveat is raised.
    data = compute_standings(session, KNOWN["season_id"][2016])
    assert data is not None
    assert data["rank_basis"] == "computed"
    assert data["tiebreak_caveat"] is True


def test_standings_streak(session: Session) -> None:
    data = compute_standings(session, KNOWN["season_id"][2016])
    assert data is not None
    mav = next(r for r in data["rows"] if r["owner_name"] == "Maverick")
    assert mav["streak"] == {"result": "W", "length": 2}


def test_standings_through_week_one(session: Session) -> None:
    data = compute_standings(session, KNOWN["season_id"][2016], through_week=1)
    assert data is not None
    assert data["through_week"] == 1
    mav = next(r for r in data["rows"] if r["owner_name"] == "Maverick")
    assert (mav["wins"], mav["points_for"]) == (1, 150.0)  # blowout week only


def test_standings_insights_robbed_and_blessed_picks(session: Session) -> None:
    # 2016: Goose is the most-robbed team (won 1, all-play expected ~1.33;
    # luck -0.33) and Slider the most-blessed (won 1, expected ~0.67; luck
    # +0.33). The picks are the voiced headline for the "Robbed & Blessed" card.
    data = standings_insights(session, KNOWN["season_id"][2016])
    assert data is not None
    assert data["available"] is True
    robbed, blessed = data["most_robbed"], data["most_blessed"]
    assert robbed is not None and blessed is not None
    assert robbed["owner_name"] == "Goose"
    assert blessed["owner_name"] == "Slider"
    # They are genuinely the extremes of the field, not an arbitrary row.
    assert robbed["luck_delta"] == min(t["luck_delta"] for t in data["teams"])
    assert blessed["luck_delta"] == max(t["luck_delta"] for t in data["teams"])
    # Each pick carries owner_id so the card can deep-link to the profile.
    assert robbed["owner_id"] == KNOWN["owner_id"]["goose"]


def test_standings_insights_ties_break_to_lower_team_id(session: Session) -> None:
    # Deterministic tie-break: among equal luck_delta values the lower team_id
    # wins both picks, so the headline is reproducible run to run.
    data = standings_insights(session, KNOWN["season_id"][2016])
    assert data is not None
    blessed_delta = data["most_blessed"]["luck_delta"]
    contenders = [t for t in data["teams"] if t["luck_delta"] == blessed_delta]
    assert data["most_blessed"]["team_id"] == min(t["team_id"] for t in contenders)
    robbed_delta = data["most_robbed"]["luck_delta"]
    contenders = [t for t in data["teams"] if t["luck_delta"] == robbed_delta]
    assert data["most_robbed"]["team_id"] == min(t["team_id"] for t in contenders)


def test_standings_insights_unplayed_season_is_a_gap_not_zero(session: Session) -> None:
    # The seeded-but-unplayed 2018 season has teams but no completed matchups:
    # schedule luck is unavailable, and the picks are absent rather than a 0.
    upcoming_id = session.execute(
        select(Season.season_id).where(Season.status == "in_progress")
    ).scalar_one()
    data = standings_insights(session, upcoming_id)
    assert data is not None
    assert data["available"] is False
    assert data["teams"] == []
    assert data.get("most_robbed") is None
    assert data.get("most_blessed") is None


def test_bracket_exposes_post_regular_season_games_with_caveat(session: Session) -> None:
    data = season_bracket(session, KNOWN["season_id"][2015])
    assert data is not None
    assert data["available"] is True
    assert data["regular_season_weeks"] == 2
    assert "Post-regular-season matchups" in data["caveat"]
    assert data["consolation_distinguished"] is True
    # Playoff bracket has rounds; single post-season week → 1 round
    pb = data["playoff_bracket"]
    assert pb is not None
    assert len(pb["rounds"]) == 1
    games = pb["rounds"][0]["games"]
    assert len(games) == 1  # one non-consolation game deduped
    champ = games[0]
    assert champ["is_consolation"] is False
    assert champ["team_a"]["owner_name"] == "Slider"
    assert champ["team_a"]["score"] == 120.0
    assert champ["winner_team_id"] == champ["team_a"]["team_id"]
    # Consolation bracket also has one round / one game
    cb = data["consolation_bracket"]
    assert cb is not None
    consol_game = cb["rounds"][0]["games"][0]
    assert consol_game["team_b"]["owner_name"] == "Iceman"


def test_bracket_split_by_connectivity_not_source_flag() -> None:
    # Two placement halves that never play each other across the post-season; the
    # championship/consolation split must come from connectivity, not is_consolation.
    def g(a: int, b: int) -> dict[str, object]:
        return {"team_a": {"team_id": a}, "team_b": {"team_id": b}}

    games = [g(1, 4), g(2, 3), g(7, 10), g(8, 9), g(1, 2), g(7, 8)]
    comps = _connected_components(games)
    assert sorted(sorted(c) for c in comps) == [[1, 2, 3, 4], [7, 8, 9, 10]]

    # Championship half (lower final ranks) leads after ordering.
    ranks: dict[int, int | None] = {1: 1, 2: 2, 3: 3, 4: 4, 7: 7, 8: 8, 9: 9, 10: 10}
    ordered = _order_components(comps, ranks)
    assert min(ordered[0]) == 1  # the {1,2,3,4} half is the championship bracket
    assert 7 in ordered[1]  # the {7..10} half is consolation


def test_bracket_gap_when_no_postseason_rows(session: Session) -> None:
    data = season_bracket(session, KNOWN["season_id"][2016])
    assert data is not None
    assert data["available"] is False
    assert data["reason"] == "bracket_unavailable"
    assert data["playoff_bracket"] is None
    assert data["consolation_bracket"] is None


def test_postseason_classification_tags_championship_and_sacko(session: Session) -> None:
    c = postseason_classification(session, KNOWN["season_id"][2015])
    assert c["consolation_distinguished"] is True

    # Championship game = the playoff-half final won by the recorded champion (Slider).
    champ_mid = c["championship_matchup_id"]
    assert champ_mid is not None
    assert c["by_matchup_id"][champ_mid]["tier"] == "championship"
    assert c["by_matchup_id"][champ_mid]["game_label"] == "Championship"

    # The toilet-bowl loser (Iceman) is the Sacko, derived from the consolation final.
    sacko = c["sacko"]
    assert sacko is not None
    assert sacko["source"] == "derived"
    assert sacko["team_id"] == KNOWN["team_id"][(2015, "ice")]

    # Every consolation matchup is tagged consolation, never championship/playoff.
    consol_tiers = {
        e["tier"] for mid, e in c["by_matchup_id"].items() if e["tier"] == "consolation"
    }
    assert consol_tiers == {"consolation"}


def test_postseason_classification_empty_when_no_postseason(session: Session) -> None:
    c = postseason_classification(session, KNOWN["season_id"][2016])
    assert c["consolation_distinguished"] is False
    assert c["by_matchup_id"] == {}
    assert c["championship_matchup_id"] is None


# --- Owners ----------------------------------------------------------------


def test_owner_career_championships(session: Session) -> None:
    careers = {c["display_name"]: c for c in list_owners_career(session)}
    assert careers["Maverick"]["championships"] == KNOWN["championships"]["mav"]  # 2
    assert careers["Slider"]["championships"] == KNOWN["championships"]["slider"]  # 1
    assert careers["Goose"]["championships"] == 0
    # Ranked by championships -> Maverick is first.
    assert list_owners_career(session)[0]["display_name"] == "Maverick"


def test_owner_career_qualification_gates_short_departed(session: Session) -> None:
    careers = {c["display_name"]: c for c in list_owners_career(session)}
    # Active managers always qualify for the "best of" rankings, regardless of
    # tenure — Viper plays a single season but is still in the league.
    assert careers["Maverick"]["is_active"] is True
    assert careers["Maverick"]["qualified"] is True
    assert careers["Viper"]["seasons_played"] == 1
    assert careers["Viper"]["qualified"] is True
    # Slider left the league after two seasons (< SIGNIFICANT_STINT_SEASONS), so a
    # short, departed stint is deprioritized — shown, but never crowned.
    assert careers["Slider"]["is_active"] is False
    assert careers["Slider"]["seasons_played"] == 2
    assert careers["Slider"]["qualified"] is False


def test_owner_trophy_case(session: Session) -> None:
    career = owner_career(session, KNOWN["owner_id"]["mav"])
    assert career is not None
    champ_years = sorted(t["season_year"] for t in career["trophy_case"] if t["is_champion"])
    assert champ_years == [2016, 2017]


# --- Head-to-head ----------------------------------------------------------


def test_pairwise_no_double_count(session: Session) -> None:
    h2h = pairwise_record(session, KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"])
    assert h2h["available"] is True
    assert h2h["games_played"] == KNOWN["h2h_mav_ice"]["games"]  # 3, not 6
    assert h2h["a_wins"] == 2
    assert h2h["b_wins"] == 1
    assert h2h["ties"] == 0
    assert h2h["a_win_pct"] == round(2 / 3, 4)
    assert h2h["highest_scoring_meeting"]["season_year"] == 2016  # 150 + 80 = 230
    assert h2h["most_lopsided_meeting"]["margin_for_a"] == 70.0


def test_pairwise_orientation_is_complementary(session: Session) -> None:
    ab = pairwise_record(session, KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"])
    ba = pairwise_record(session, KNOWN["owner_id"]["ice"], KNOWN["owner_id"]["mav"])
    assert ab["a_wins"] == ba["b_wins"]
    assert round(ab["a_win_pct"] + ba["a_win_pct"], 4) == 1.0  # no ties


def test_rivalry_matrix_symmetry(session: Session) -> None:
    matrix = rivalry_matrix(session)
    cell = {(c["a"], c["b"]): c for c in matrix["cells"]}
    mav, ice = KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"]
    assert cell[(mav, mav)]["a_win_pct"] is None  # diagonal blank
    assert round(cell[(mav, ice)]["a_win_pct"] + cell[(ice, mav)]["a_win_pct"], 4) == 1.0


# --- Records book ----------------------------------------------------------


def test_records_score_superlatives(session: Session) -> None:
    book = records_book(session)
    assert book["highest_team_score"]["value"] == KNOWN["highest_team_score"]  # 160.4
    assert book["highest_team_score"]["owner_name"] == "Maverick"
    assert book["biggest_blowout"]["value"] == KNOWN["biggest_blowout_margin"]  # 70.0
    # Win-margin records name both sides (Maverick 150 def. Iceman 80, 2016 wk1).
    assert book["biggest_blowout"]["winner_name"] == "Maverick 2016"
    assert book["biggest_blowout"]["loser_name"] == "Iceman 2016"
    assert book["narrowest_win"]["value"] == 1.0
    # Best player week is the highest *started* player's week, scored the box-score
    # way. Lamar's higher scored row (35.5) is excluded — he was never in a lineup.
    assert book["best_player_week"]["value"] == KNOWN["highest_started_player_week"]  # 30.0
    assert book["best_player_week"]["player_name"] == "Christian McCaffrey"
    assert book["best_player_week"]["team_name"] == "Maverick 2016"
    assert book["best_player_week"]["owner_name"] == "Maverick"


def test_records_record_only(session: Session) -> None:
    book = records_book(session)
    assert book["most_championships"]["value"] == 2
    assert book["most_championships"]["owner_name"] == "Maverick"
    assert book["best_season_points_for"]["value"] == 270.0  # Maverick 2016
    assert book["worst_season_points_for"]["value"] == 170.0  # Iceman 2016
    assert book["longest_win_streak"] == {
        "available": True,
        "value": 3,
        "owner_id": KNOWN["owner_id"]["mav"],
        "owner_name": "Maverick",
    }
    assert book["longest_loss_streak"]["value"] == 4  # Iceman, 2015-2016
    assert book["longest_loss_streak"]["owner_name"] == "Iceman"


def test_records_closest_rivalry(session: Session) -> None:
    # Maverick vs Iceman is the most-played pair (3 meetings) -> wins the
    # "more games first, then nearest 0.5" tiebreak, ahead of the 2-game pairs.
    rivalry = records_book(session)["closest_rivalry"]
    assert rivalry["available"] is True
    assert rivalry["games_played"] == KNOWN["h2h_mav_ice"]["games"]  # 3
    names = {rivalry["owner_a"]["display_name"], rivalry["owner_b"]["display_name"]}
    assert names == {"Maverick", "Iceman"}


def test_records_only_use_scored_era(session: Session) -> None:
    book = records_book(session)
    assert book["scored_era"] == KNOWN["seasons_scored"]
    # The best player week must come from a scored season, never a generic
    # present-but-unscored gap season.
    assert book["best_player_week"]["season_year"] in set(KNOWN["seasons_scored"])


def test_championships_use_season_correct_team_name(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Championship history must render the period-correct slot name, not the
    DB's latest canonical team_name (regression for the 2024 champion showing
    its current name instead of the name it won under)."""
    # The fixture's 2016 champion (Maverick, slot abbrev "MAV") carries the
    # canonical alias "Maverick 2016". Inject a divergent historical slot name
    # so we can prove championships() resolves it rather than the raw column.
    monkeypatch.setitem(HISTORICAL_TEAM_NAMES, (2016, "MAV"), "Putting the CAP in CHAMP")
    by_year = {e["season_year"]: e for e in championships(session)["seasons"]}
    assert by_year[2016]["champion"]["team_name"] == "Putting the CAP in CHAMP"


# --- Players + gap behavior ------------------------------------------------


def test_player_scoring_unscored_season_is_a_gap(session: Session) -> None:
    data = player_scoring(session, KNOWN["player_id"]["lamar"], 2015)
    assert data is not None
    assert data["available"] is False
    assert data["reason"] == "season_unscored"
    assert data["weeks"] == []  # never zeros


def test_player_scoring_scored_season(session: Session) -> None:
    data = player_scoring(session, KNOWN["player_id"]["jjet"], 2017)
    assert data is not None
    assert data["available"] is True
    assert data["total_points"] == KNOWN["top_scorer_2017_season_total"]  # 58.0


def test_player_scoring_includes_authoritative_zero_weeks(session: Session) -> None:
    data = player_scoring(session, KNOWN["player_id"]["dnp"], 2017)
    assert data is not None
    assert data["available"] is True
    assert data["total_points"] == 0.0
    assert data["weeks"] == [
        {
            "week": 1,
            "points": 0.0,
            "breakdown": {},
            "zero_reason": "did_not_play",
            "zero_detail": None,
        },
        {
            "week": 2,
            "points": 0.0,
            "breakdown": {},
            "zero_reason": "bye",
            "zero_detail": None,
        },
    ]


def test_availability_non_current_season_is_a_gap(session: Session) -> None:
    # Fixture current season is 2017; 2016 availability is not reconstructable.
    data = availability(session, KNOWN["player_id"]["jjet"], 2016)
    assert data is not None
    assert data["available"] is False
    assert data["reason"] == "availability_history_not_reconstructable"


def test_availability_current_season_present(session: Session) -> None:
    data = availability(session, KNOWN["player_id"]["jjet"], 2017)
    assert data is not None
    assert data["available"] is True
    assert data["weeks"][0]["status"] == "owned"


def test_player_index_scopes_to_league_relevance(session: Session) -> None:
    # cmc is rostered → in the league index; jjet is scored-but-never-rostered →
    # excluded by default, present only under scope=all.
    league = {r["player_id"] for r in list_player_index(session, scope="league")}
    assert KNOWN["player_id"]["cmc"] in league
    assert KNOWN["player_id"]["jjet"] not in league
    everyone = {r["player_id"] for r in list_player_index(session, scope="all")}
    assert KNOWN["player_id"]["jjet"] in everyone


def test_player_index_row_enrichment(session: Session) -> None:
    (row,) = list_player_index(session, name="McCaffrey")
    assert (row["first_rostered_season"], row["last_rostered_season"]) == (2016, 2017)
    assert "has_scored" not in row


def test_ownership_timeline_collapses_into_spans(session: Session) -> None:
    # cmc is rostered weeks 1-2 of 2016 (contiguous → one collapsed span) and week 1
    # of 2017 → two spans, one per season, never one row per week.
    data = ownership_timeline(session, KNOWN["player_id"]["cmc"])
    assert data is not None
    assert (data["first_rostered_season"], data["last_rostered_season"]) == (2016, 2017)
    assert [(s["season_year"], s["week_start"], s["week_end"]) for s in data["events"]] == [
        (2016, 1, 2),
        (2017, 1, 1),
    ]
    assert data["events"][0]["owner_name"] == "Maverick"
    assert data["events"][0]["team_name"] == "Maverick 2016"
