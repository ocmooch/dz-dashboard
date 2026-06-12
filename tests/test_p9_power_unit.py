"""P9 — power-ranking analytics unit tests against hand-computed known answers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.power import (
    POWER_WEIGHTS,
    RECENT_WEEKS,
    _zscores,
    power_ranking,
    power_timeline,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --- The pure z-score helper (no DB) ---------------------------------------


def test_zscores_population_standardisation() -> None:
    # mean 2.5, population stdev sqrt(1.25)=1.118034 → symmetric ±.
    zs = _zscores([1.0, 2.0, 3.0, 4.0])
    assert [round(z, 4) for z in zs] == [-1.3416, -0.4472, 0.4472, 1.3416]
    # Centred values always sum to ~0.
    assert round(sum(zs), 9) == 0.0


def test_zscores_no_spread_is_zero() -> None:
    # No spread (or a single team) → 0, never a division error.
    assert _zscores([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]
    assert _zscores([7.0]) == [0.0]
    assert _zscores([]) == []


def test_weights_sum_to_one() -> None:
    assert round(sum(POWER_WEIGHTS.values()), 9) == 1.0


# --- Power ranking over the fixture ----------------------------------------


def test_power_ranking_2016_known_scores(session: Session) -> None:
    pr = power_ranking(session, KNOWN["season_id"][2016])
    assert pr is not None
    assert pr["through_week"] == 2
    assert pr["weights"] == POWER_WEIGHTS
    assert "z-score" in pr["explainer"]

    by_owner = {r["owner_name"]: r for r in pr["rows"]}
    exp = KNOWN["power_2016"]
    name = {"mav": "Maverick", "goose": "Goose", "slider": "Slider", "ice": "Iceman"}

    # Top of the board: Maverick (best record AND best scoring).
    mav = by_owner["Maverick"]
    assert mav["rank"] == 1
    assert mav["power_score"] == exp["mav"]["power_score"]
    assert mav["points_for_per_game"] == exp["mav"]["pf_per_game"]
    assert mav["all_play_win_pct"] == 1.0
    assert mav["z_all_play_win_pct"] == 1.3416
    assert mav["z_win_pct"] == exp["mav"]["z_win"]
    # Only 2 weeks played → recent window == whole season.
    assert mav["recent_points_for_per_game"] == mav["points_for_per_game"]

    # Every team's score and rank match the hand computation.
    for key, e in exp.items():
        row = by_owner[name[key]]
        assert row["power_score"] == e["power_score"]
        assert row["rank"] == e["rank"]
        assert row["points_for_per_game"] == e["pf_per_game"]

    # Rows are returned in power order.
    assert [r["rank"] for r in pr["rows"]] == [1, 2, 3, 4]
    assert [r["power_score"] for r in pr["rows"]] == sorted(
        (r["power_score"] for r in pr["rows"]), reverse=True
    )


def test_power_matches_standings_here_so_delta_is_zero(session: Session) -> None:
    # In this small fixture the scoring order equals the win order, so the model
    # agrees with the standings and no team is a riser/faller.
    pr = power_ranking(session, KNOWN["season_id"][2016])
    assert pr is not None
    for r in pr["rows"]:
        assert r["standings_rank"] == r["rank"]
        assert r["rank_delta"] == 0


def test_power_ranking_works_on_unscored_season(session: Session) -> None:
    # 2015 has no player-level scoring, but team scores exist — power uses those,
    # so it still ranks (proving it does not depend on the scored era).
    pr = power_ranking(session, KNOWN["season_id"][2015])
    assert pr is not None
    assert len(pr["rows"]) == 4
    assert all(isinstance(r["power_score"], float) for r in pr["rows"])


def test_power_through_week_one(session: Session) -> None:
    pr = power_ranking(session, KNOWN["season_id"][2016], through_week=1)
    assert pr is not None
    assert pr["through_week"] == 1
    assert RECENT_WEEKS == 3


def test_power_ranking_unknown_season_is_none(session: Session) -> None:
    assert power_ranking(session, 99999) is None


# --- Power timeline --------------------------------------------------------


def test_power_timeline_has_a_point_per_week(session: Session) -> None:
    tl = power_timeline(session, KNOWN["season_id"][2016])
    assert tl is not None
    assert tl["regular_season_weeks"] == 2
    assert len(tl["teams"]) == 4
    for team in tl["teams"]:
        assert [p["week"] for p in team["points"]] == [1, 2]
        assert all(1 <= p["rank"] <= 4 for p in team["points"])

    # Maverick (the eventual leader) ends the season ranked #1.
    mav = next(t for t in tl["teams"] if t["owner_name"] == "Maverick")
    assert mav["points"][-1]["rank"] == 1


def test_power_timeline_unknown_season_is_none(session: Session) -> None:
    assert power_timeline(session, 99999) is None
