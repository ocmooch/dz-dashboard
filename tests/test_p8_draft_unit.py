"""P8 — draft analytics unit tests against hand-computed known answers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ff_dashboard.analytics.draft import (
    VALUE_SLOT_WINDOW,
    _classify_pick_scoring,
    _did_not_play_detail,
    _expected_by_slot,
    best_worst_picks,
    draft_board,
    draft_value,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --- The pure pick-scoring classifier (no DB) ------------------------------


def _player(position: str = "WR", gsis_id: str | None = "00-0000001") -> SimpleNamespace:
    return SimpleNamespace(position=position, gsis_id=gsis_id)


def test_classify_scored_pick_passes_through() -> None:
    out = _classify_pick_scoring(
        player=_player(),
        scored_points=123.456,
        season_is_scored=True,
        played=True,
        roster_slots={"WR"},
    )
    assert out["season_points"] == 123.46  # rounded
    assert out["available"] is True
    assert out["reason"] is None
    assert out["zero_reason"] is None


def test_classify_unscored_season_is_a_gap() -> None:
    out = _classify_pick_scoring(
        player=_player(),
        scored_points=None,
        season_is_scored=False,
        played=False,
        roster_slots=set(),
    )
    assert out["season_points"] is None
    assert out["available"] is False
    assert out["reason"] == "season_unscored"


def test_classify_defense_without_stats_is_always_a_gap() -> None:
    # A DST can never have a legitimate season-long 0 — even with a raw line it
    # is a scoring gap, never a real zero, so DEF takes precedence over "played".
    out = _classify_pick_scoring(
        player=_player(position="DEF", gsis_id=None),
        scored_points=None,
        season_is_scored=True,
        played=True,
        roster_slots={"DEF"},
    )
    assert out["season_points"] is None
    assert out["available"] is False
    assert out["reason"] == "team_defense_not_scored"
    assert out["zero_reason"] is None


def test_classify_played_but_unscored_is_a_gap() -> None:
    out = _classify_pick_scoring(
        player=_player(),
        scored_points=None,
        season_is_scored=True,
        played=True,
        roster_slots={"WR"},
    )
    assert out["reason"] == "player_unscored"
    assert out["available"] is False


def test_classify_never_played_weak_identity_is_unresolved() -> None:
    for gsis in (None, "", "   "):
        out = _classify_pick_scoring(
            player=_player(gsis_id=gsis),
            scored_points=None,
            season_is_scored=True,
            played=False,
            roster_slots={"BN"},
        )
        assert out["reason"] == "player_identity_unresolved"
        assert out["available"] is False


def test_classify_never_played_real_player_is_a_genuine_zero() -> None:
    # Drafted, fully identified, scored season, no game stats all year (a torn
    # ACL in camp): a real 0.0 the board shows with a note, not a hidden gap.
    out = _classify_pick_scoring(
        player=_player(gsis_id="00-0032054"),
        scored_points=None,
        season_is_scored=True,
        played=False,
        roster_slots={"BN"},
    )
    assert out["season_points"] == 0.0
    assert out["available"] is True
    assert out["reason"] is None
    assert out["zero_reason"] == "did_not_play_season"
    assert "active bench" in (out["zero_detail"] or "")


def test_did_not_play_detail_distinguishes_reserve_from_bench() -> None:
    assert "reserve / IR" in _did_not_play_detail({"RES"})
    assert "active bench" in _did_not_play_detail({"BN"})
    # No roster rows after the draft → just the base note, no carry phrasing.
    base = _did_not_play_detail(set())
    assert "reserve / IR" not in base and "active bench" not in base


# --- The pure expectation helper (no DB) -----------------------------------


def test_expected_by_slot_windows_neighbours() -> None:
    # Two seasons' worth of picks at overalls 1..4; early slots score more, so
    # the windowed mean rises toward the top of the draft — the intended shape.
    history = [
        (1, 60.0),
        (2, 50.0),
        (3, 40.0),
        (4, 30.0),
        (1, 58.0),
        (2, 52.0),
        (3, 38.0),
        (4, 32.0),
    ]
    expected = _expected_by_slot(history)
    # slot 1 pools overalls within ±2 → {1,2,3}: (60+58+50+52+40+38)/6 = 49.6667
    assert round(expected[1], 4) == 49.6667
    # slot 4 pools {2,3,4}: (50+52+40+38+30+32)/6 = 40.3333
    assert round(expected[4], 4) == 40.3333
    # higher (better) slot has the higher expectation
    assert expected[1] > expected[4]


def test_expected_by_slot_empty() -> None:
    assert _expected_by_slot([]) == {}
    assert VALUE_SLOT_WINDOW == 2


# --- Board over the fixture ------------------------------------------------


def test_board_orders_picks_and_resolves_players(session: Session) -> None:
    board = draft_board(session, KNOWN["season_id"][2016])
    assert board is not None
    assert board["available"] is True
    assert board["num_teams"] == 4
    # Four teams, four picks → a single round.
    assert [r["round"] for r in board["rounds"]] == [1]
    picks = board["rounds"][0]["picks"]
    assert [p["overall"] for p in picks] == [1, 2, 3, 4]
    assert [p["pick_in_round"] for p in picks] == [1, 2, 3, 4]
    pid = KNOWN["player_id"]
    assert [p["player_id"] for p in picks] == [
        pid["kelce"],
        pid["lamar"],
        pid["jjet"],
        pid["cmc"],
    ]
    # McCaffrey was Maverick's rostered draftee — board and roster agree.
    cmc = picks[-1]
    assert cmc["owner_name"] == "Maverick"
    assert cmc["season_points"] == 55.0


def test_board_gap_when_no_draft_captured(session: Session) -> None:
    # 2015 is unscored AND has no draft transactions → the honest gap, not zeros.
    board = draft_board(session, KNOWN["season_id"][2015])
    assert board is not None
    assert board["available"] is False
    assert board["reason"] == "draft_not_captured"
    assert board["rounds"] == []
    # 2017 is scored but its draft was likewise not captured.
    board17 = draft_board(session, KNOWN["season_id"][2017])
    assert board17 is not None
    assert board17["available"] is False


def test_board_unknown_season_is_none(session: Session) -> None:
    assert draft_board(session, 99999) is None


# --- Value (steals / busts) ------------------------------------------------


def test_value_identifies_steal_and_bust(session: Session) -> None:
    value = draft_value(session, KNOWN["season_id"][2016])
    assert value is not None
    assert value["available"] is True
    assert value["slot_window"] == VALUE_SLOT_WINDOW
    assert "regular-season fantasy points" in value["definition"]

    steal = value["steals"][0]
    assert steal["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert steal["overall"] == KNOWN["draft_top_steal"]["overall"]
    assert steal["value"] == KNOWN["draft_top_steal"]["value"]  # 8.33

    bust = value["busts"][0]
    assert bust["player_name"] == KNOWN["draft_top_bust"]["player"]
    assert bust["overall"] == KNOWN["draft_top_bust"]["overall"]
    assert bust["value"] == KNOWN["draft_top_bust"]["value"]  # -13.67

    # Full pick list is sorted by value, highest first.
    values = [p["value"] for p in value["picks"]]
    assert values == sorted(values, reverse=True)


# --- Records book best/worst ever ------------------------------------------


def test_best_worst_picks_ever(session: Session) -> None:
    rec = best_worst_picks(session)
    assert rec["available"] is True
    assert rec["best_picks"][0]["player_name"] == KNOWN["draft_top_steal"]["player"]
    assert rec["worst_picks"][0]["player_name"] == KNOWN["draft_top_bust"]["player"]
