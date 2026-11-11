"""Rivalry insight bands — league-wide reducers over the pairwise history.

Hand-computed against the fixture league (see ``tests/conftest.py``). The fixture's
meetings give every superlative a single known answer, and the min-sample gates are
exercised on both sides (a real rivalry passes; a thin one is filtered).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ff_dashboard.analytics import rivalries
from ff_dashboard.analytics.rivalries import (
    manager_nemeses,
    playoff_rivalries,
    rivalry_insights,
    rivalry_intensity,
    rivalry_records,
    rivalry_streaks,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _oid(key: str) -> int:
    return KNOWN["owner_id"][key]


def test_records_superlatives(session: Session) -> None:
    rec = rivalry_records(session)
    assert rec["available"] is True

    # Closest game ever: Goose 100.5 - Slider 99.5 (2016 wk1), margin 1.0.
    closest = rec["closest_game"]
    assert closest["margin"] == 1.0
    assert closest["winner"]["owner_id"] == _oid("goose")
    assert closest["loser"]["owner_id"] == _oid("slider")
    assert closest["matchup_id"] == KNOWN["matchup_id"][(2016, 1, "goose")]

    # Biggest beating: Maverick 150 - Iceman 80 (2016 wk1), margin 70.0.
    blow = rec["biggest_blowout"]
    assert blow["margin"] == KNOWN["biggest_blowout_margin"] == 70.0
    assert blow["winner"]["owner_id"] == _oid("mav")
    assert blow["loser"]["owner_id"] == _oid("ice")
    assert blow["matchup_id"] == KNOWN["matchup_id"][(2016, 1, "mav")]

    # Highest-scoring duel: Maverick 160.4 + Viper 120 (2017 wk1) = 280.4.
    duel = rec["highest_scoring_duel"]
    assert duel["combined"] == 280.4
    assert duel["winner"]["owner_id"] == _oid("mav")

    # Most-played is a ranked list; Maverick vs Iceman (3 games) leads.
    most = rec["most_played"]
    assert most[0]["games"] == 3
    assert {most[0]["owner_a"]["owner_id"], most[0]["owner_b"]["owner_id"]} == {
        _oid("mav"),
        _oid("ice"),
    }
    # The five active-pair rivalries fill the top tier, so short-stint departed
    # Slider's pairings are deprioritized out of the top-N (never hidden — they
    # simply rank below every active pairing).
    top_ids = {o for it in most for o in (it["owner_a"]["owner_id"], it["owner_b"]["owner_id"])}
    assert _oid("slider") not in top_ids

    # Dead-even needs a real series (MIN_DEAD_EVEN_GAMES=4); the small fixture has
    # none, so it's an honest empty list rather than a thin/lopsided pair.
    assert rec["dead_even"] == []


def test_dead_even_prefers_balance_over_volume(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rivalries, "MIN_DEAD_EVEN_GAMES", 2)
    rec = rivalry_records(session)
    de = rec["dead_even"]
    assert de, "expected dead-even pairs once the sample gate is lowered"
    top = de[0]
    # The headline is a genuinely even (1-1) series, not lopsided Maverick vs
    # Iceman (2-1) despite it being the most-played pair.
    assert top["a_wins"] == top["b_wins"]
    assert {top["owner_a"]["owner_id"], top["owner_b"]["owner_id"]} != {_oid("mav"), _oid("ice")}
    # Departed-short-stint (Slider) pairings rank below the active ones.
    assert _oid("slider") not in {top["owner_a"]["owner_id"], top["owner_b"]["owner_id"]}


def test_streaks_longest_and_active(session: Session) -> None:
    streaks = rivalry_streaks(session)
    assert streaks["available"] is True
    # The longest H2H run in the fixture is 2 (Maverick beat Iceman 2015→2016,
    # and Slider beat Iceman in both their meetings).
    assert streaks["longest"]["length"] == 2
    # The longest run carries both ends so the UI can deep-link a cross-season
    # run start → end, not just point at the last game.
    assert streaks["longest"]["from_matchup_id"] is not None
    assert streaks["longest"]["last_matchup_id"] is not None
    # No run reaches the active-domination gate (3), so the active list is empty —
    # honest emptiness, not a fabricated streak.
    assert streaks["active"] == []


def test_intensity_gate_filters_thin_rivalries(session: Session) -> None:
    # No fixture pair reaches MIN_INTENSITY_GAMES (4), so the leaderboard is a
    # gap, never a list padded with 2-game pairs.
    out = rivalry_intensity(session)
    assert out["available"] is False
    assert out["reason"] == "insufficient_rivalry_history"


def test_intensity_math_when_gate_lowered(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rivalries, "MIN_INTENSITY_GAMES", 2)
    out = rivalry_intensity(session)
    assert out["available"] is True
    board = out["leaderboard"]
    assert board, "expected ranked rivalries once the gate is lowered"
    # Prominent pairings lead: tiers are non-increasing, and within each tier the
    # board is ranked hottest-first. (A hot Slider pairing still sinks below a
    # cooler active one — active-manager focus without hiding history.)
    tiers = [row["pair_tier"] for row in board]
    assert tiers == sorted(tiers, reverse=True)
    for t in set(tiers):
        tier_heats = [row["heat"] for row in board if row["pair_tier"] == t]
        assert tier_heats == sorted(tier_heats, reverse=True)
    for row in board:
        assert 0.0 <= row["heat"] <= 100.0
        assert all(0.0 <= v <= 1.0 for v in row["components"].values())
        assert row["last_meeting"]["matchup_id"] is not None
        # Refs carry activity so the UI can dim departed managers in place.
        assert "is_active" in row["owner_a"]


def test_nemeses_active_only_with_min_sample(session: Session) -> None:
    out = manager_nemeses(session)
    assert out["available"] is True
    by_owner = {row["owner"]["owner_id"]: row for row in out["managers"]}

    # Only Maverick↔Iceman clears the 3-game nemesis gate. Maverick leads it 2-1,
    # so Iceman is his favorite victim and he has no qualifying nemesis.
    mav = by_owner[_oid("mav")]
    assert mav["nemesis"] is None
    assert mav["favorite_victim"]["opponent"]["owner_id"] == _oid("ice")
    assert mav["favorite_victim"]["wins"] == 2

    # The mirror: Iceman's nemesis is Maverick, no favorite victim.
    ice = by_owner[_oid("ice")]
    assert ice["favorite_victim"] is None
    assert ice["nemesis"]["opponent"]["owner_id"] == _oid("mav")
    assert ice["nemesis"]["win_pct"] == pytest.approx(1 / 3, abs=1e-4)

    # Goose has no opponent past the gate → both sides are honest gaps, not zeros.
    goose = by_owner[_oid("goose")]
    assert goose["nemesis"] is None
    assert goose["favorite_victim"] is None


def test_playoff_rivalries(session: Session) -> None:
    out = playoff_rivalries(session)
    assert out["available"] is True
    rivs = out["rivalries"]
    # Only the **true** playoff pairing surfaces: Slider/Maverick (championship). The
    # Goose/Iceman consolation ("toilet bowl") game is not a playoff achievement and
    # must NOT appear as a playoff rivalry.
    assert len(rivs) == 1

    pairs = {frozenset({r["owner_a"]["owner_id"], r["owner_b"]["owner_id"]}): r for r in rivs}
    assert frozenset({_oid("goose"), _oid("ice")}) not in pairs
    ms = pairs[frozenset({_oid("mav"), _oid("slider")})]
    assert ms["playoff_meetings"] == 1
    assert ms["last_meeting"]["season_year"] == 2015
    # Slider beat Maverick in the 2015 final; oriented to the lower id (Maverick).
    assert ms["a_wins"] == 0
    assert ms["b_wins"] == 1


def test_bundle_carries_every_band(session: Session) -> None:
    bundle = rivalry_insights(session)
    assert set(bundle) == {"records", "streaks", "intensity", "nemeses", "playoffs"}
