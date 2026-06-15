"""Per-owner "Your Story" superlatives — hand-computed against the fixture league.

The fixture (see ``tests/conftest.py``) gives Maverick a rich story (a 70-point
beating, a playoff heartbreak, a favourite victim, a lucky season) and Viper a
sparse-but-valid one (no wins, an unlucky season). Both sides of every min-sample
and sign gate are exercised, and the epithet thresholds are checked just above and
below each bar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.owner_story import (
    EPITHET_BRIDESMAID_RUNNERUPS,
    EPITHET_DYNASTY_TITLES,
    EPITHET_LUCKY_DELTA,
    MIN_EPITHET_SEASONS,
    OwnerFingerprint,
    assign_epithet,
    owner_story,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _oid(key: str) -> int:
    return KNOWN["owner_id"][key]


def _mid(year: int, week: int, team_key: str) -> int:
    return KNOWN["matchup_id"][(year, week, team_key)]


# --- Maverick: the rich, known-answer case ----------------------------------


def test_signature_win_is_biggest_beating(session: Session) -> None:
    story = owner_story(session, _oid("mav"))
    assert story is not None and story["available"] is True
    sig = story["signature_win"]
    assert sig is not None
    assert sig["opponent"]["owner_id"] == _oid("ice")
    assert sig["owner_score"] == 150.0
    assert sig["opponent_score"] == 80.0
    assert sig["margin"] == 70.0
    assert sig["matchup_id"] == _mid(2016, 1, "mav")


def test_heartbreak_prefers_playoff_loss(session: Session) -> None:
    story = owner_story(session, _oid("mav"))
    assert story is not None
    hb = story["heartbreak"]
    # Maverick's only playoff loss is the 2015 championship to Slider (by 10),
    # chosen over his narrower 5-point regular-season loss to Iceman.
    assert hb is not None
    assert hb["opponent"]["owner_id"] == _oid("slider")
    assert hb["is_playoff"] is True
    assert hb["margin"] == 10.0
    assert hb["season_year"] == 2015
    assert hb["matchup_id"] is not None


def test_high_water_mark(session: Session) -> None:
    story = owner_story(session, _oid("mav"))
    assert story is not None
    hw = story["high_water_mark"]
    assert hw is not None
    assert hw["score"] == KNOWN["highest_team_score"]  # 160.4, 2017 wk1
    assert hw["season_year"] == 2017
    assert hw["matchup_id"] == _mid(2017, 1, "mav")


def test_favorite_victim_and_no_nemesis(session: Session) -> None:
    story = owner_story(session, _oid("mav"))
    assert story is not None
    # Only Iceman clears the 3-game bar (Mav is 2-1); a single >.500 opponent
    # resolves to favourite victim, and the nemesis is absent rather than forced.
    vic = story["favorite_victim"]
    assert vic is not None
    assert vic["opponent"]["owner_id"] == _oid("ice")
    assert (vic["wins"], vic["losses"], vic["ties"]) == (2, 1, 0)
    assert story["nemesis"] is None


def test_luckiest_season_shown_unluckiest_absent(session: Session) -> None:
    story = owner_story(session, _oid("mav"))
    assert story is not None
    lucky = story["luckiest_season"]
    assert lucky is not None
    assert lucky["season_year"] == 2015
    assert lucky["luck_delta"] == 0.33
    # Maverick never had a negative-luck season → no unlucky line (not a fake 0).
    assert story["unluckiest_season"] is None


# --- Viper: the sparse-but-valid case ---------------------------------------


def test_sparse_owner_bundle_is_mostly_empty_but_valid(session: Session) -> None:
    story = owner_story(session, _oid("viper"))
    assert story is not None
    # No wins → no signature win; thin pairings → no nemesis/victim.
    assert story["signature_win"] is None
    assert story["nemesis"] is None
    assert story["favorite_victim"] is None
    # Closest loss with no playoff history → narrowest regular-season loss (Goose, 30).
    hb = story["heartbreak"]
    assert hb is not None
    assert hb["opponent"]["owner_id"] == _oid("goose")
    assert hb["is_playoff"] is False
    assert hb["margin"] == 30.0
    # Opposite sign gate: an unlucky season is shown, the lucky line is absent.
    assert story["unluckiest_season"] is not None
    assert story["unluckiest_season"]["luck_delta"] == -0.67
    assert story["luckiest_season"] is None
    # Still a valid, available bundle (heartbreak / high-water / unlucky present).
    assert story["available"] is True


def test_unknown_owner_returns_none(session: Session) -> None:
    assert owner_story(session, 999999) is None


# --- Epithet proposal: thresholds fire above the bar, not below -------------


def _fp(**kw: object) -> OwnerFingerprint:
    base: dict[str, object] = {
        "seasons_played": MIN_EPITHET_SEASONS,
        "championships": 0,
        "runner_ups": 0,
        "best_finish": None,
        "win_pct": None,
        "best_luck_delta": None,
        "worst_luck_delta": None,
    }
    base.update(kw)
    return OwnerFingerprint(**base)  # type: ignore[arg-type]


def test_epithet_requires_min_tenure() -> None:
    assert assign_epithet(_fp(seasons_played=MIN_EPITHET_SEASONS - 1, championships=5)) is None


def test_epithet_dynasty_fires_at_threshold() -> None:
    assert assign_epithet(_fp(championships=EPITHET_DYNASTY_TITLES))["label"] == "The Dynasty"
    # One title short does not fire the Dynasty archetype.
    assert assign_epithet(_fp(championships=EPITHET_DYNASTY_TITLES - 1)) is None


def test_epithet_bridesmaid_fires_only_without_a_title() -> None:
    assert assign_epithet(_fp(runner_ups=EPITHET_BRIDESMAID_RUNNERUPS))["label"] == "The Bridesmaid"
    # A single runner-up is below the bar.
    assert assign_epithet(_fp(runner_ups=EPITHET_BRIDESMAID_RUNNERUPS - 1)) is None
    # A title disqualifies the Bridesmaid even with the runner-ups.
    assert assign_epithet(_fp(championships=1, runner_ups=EPITHET_BRIDESMAID_RUNNERUPS)) is None


def test_epithet_lucky_devil_fires_at_threshold() -> None:
    assert assign_epithet(_fp(best_luck_delta=EPITHET_LUCKY_DELTA))["label"] == "The Lucky Devil"
    assert assign_epithet(_fp(best_luck_delta=EPITHET_LUCKY_DELTA - 0.1)) is None
