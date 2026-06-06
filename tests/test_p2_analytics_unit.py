"""P2 — analytics unit tests against the fixture's hand-computed known answers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.head_to_head import pairwise_record, rivalry_matrix
from ff_dashboard.analytics.owners import list_owners_career, owner_career
from ff_dashboard.analytics.players import (
    availability,
    list_player_index,
    ownership_timeline,
    player_scoring,
)
from ff_dashboard.analytics.records import records_book
from ff_dashboard.analytics.standings import compute_standings
from tests.conftest import KNOWN

if TYPE_CHECKING:
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


# --- Owners ----------------------------------------------------------------


def test_owner_career_championships(session: Session) -> None:
    careers = {c["display_name"]: c for c in list_owners_career(session)}
    assert careers["Maverick"]["championships"] == KNOWN["championships"]["mav"]  # 2
    assert careers["Slider"]["championships"] == KNOWN["championships"]["slider"]  # 1
    assert careers["Goose"]["championships"] == 0
    # Ranked by championships -> Maverick is first.
    assert list_owners_career(session)[0]["display_name"] == "Maverick"


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
    assert book["narrowest_win"]["value"] == 1.0
    assert book["best_player_week"]["value"] == KNOWN["highest_player_week"]  # 35.5
    assert book["best_player_week"]["player_name"] == "Lamar Jackson"


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
    assert book["scored_era"] == KNOWN["seasons_scored"]  # [2016, 2017]
    # The best player week must come from a scored season, never 2015.
    assert book["best_player_week"]["season_year"] in {2016, 2017}


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
    assert row["has_scored"] is True


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
