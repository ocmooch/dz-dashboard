"""F-43 — automated data-gap / correctness validation harness.

Cross-checks the dashboard's coverage affordances and computed windows against
the database, asserting the coverage *truths* the 2026-06 in-browser review
found the honesty layer over-claiming (F-16/F-22/F-25/F-31/F-35). The
assertions are **invariants/relationships**, not fixture-specific magic numbers,
so they hold on the real DB too:

* per-player scoring is absent before 2016 while team totals are present
  (F-16/F-31/F-35 — "complete 2010-2015 team data must not read as incomplete");
* the player index never leaks never-rostered players (F-25/F-44);
* the records windows match their coverage — team records span all team-totals
  seasons, player records stay in the scored era (F-22);
* the ``dst_scoring_complete`` flag agrees with the scored DEF rows (F-48).

Read-only, against the conftest fixture (2015 unscored; 2016/2017 scored).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Matchup, Season
from sqlalchemy import func, select

from ff_dashboard.analytics.coverage import (
    compute_coverage,
    dst_scoring_complete,
    seasons_present,
    seasons_scored,
    seasons_with_dst_scored,
)
from ff_dashboard.analytics.players import list_player_index
from ff_dashboard.analytics.records import (
    records_book,
    scored_window,
    team_record_window,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# The player-scored era begins in 2016; the pipeline never reconstructed
# per-player fantasy points for 2010-2015 (only team totals exist). This is the
# coverage truth every pre-2016 affordance must respect.
FIRST_SCORED_YEAR = 2016


def _matchups_with_team_scores(session: Session, year: int) -> int:
    """Count matchup rows carrying a real team score for a given season year."""
    return int(
        session.execute(
            select(func.count(Matchup.matchup_id))
            .join(Season, Season.season_id == Matchup.season_id)
            .where(Season.year == year, Matchup.team_score.is_not(None))
        ).scalar_one()
    )


def test_player_scoring_absent_pre_2016(session: Session) -> None:
    """No season before 2016 carries per-player scoring; scored ⊆ present."""
    scored = seasons_scored(session)
    present = seasons_present(session)
    assert scored, "fixture must have at least one scored season"
    assert min(scored) >= FIRST_SCORED_YEAR
    assert set(scored) <= set(present)
    # The exact F-16/F-31 case: a present-but-unscored historical season exists,
    # so the affordance has something honest to scope to.
    assert set(present) - set(scored), "expected an unscored historical season"


def test_team_totals_present_in_unscored_era(session: Session) -> None:
    """Present-but-unscored seasons still carry real team scores (F-16/F-35).

    The explicit gap case: an unscored season (2015 in the fixture) has matchups
    with non-null team scores, so team results/standings/rosters are complete
    even where per-player scoring is absent. Labeling those seasons "incomplete"
    is the over-claim the review caught.
    """
    scored = set(seasons_scored(session))
    unscored_present = [y for y in seasons_present(session) if y not in scored]
    assert unscored_present, "fixture must include an unscored historical season"
    for year in unscored_present:
        assert _matchups_with_team_scores(session, year) > 0, (
            f"unscored season {year} must still have complete team scores"
        )


def test_index_has_no_never_rostered_players(session: Session) -> None:
    """``scope=league`` never leaks players nobody in the league rostered (F-25/F-44).

    Every league-scoped row has a non-null rostered span; the broader
    ``scope=all`` universe does include never-rostered players, proving the
    filter is what excludes them (not an empty DB).
    """
    league = list_player_index(session, scope="league", limit=1000)
    universe = list_player_index(session, scope="all", limit=1000)
    assert league, "fixture must have at least one rostered player"
    assert all(r["last_rostered_season"] is not None for r in league)
    assert len(league) < len(universe), "scope=all must be a superset"
    assert any(r["last_rostered_season"] is None for r in universe), (
        "fixture must contain a never-rostered player for the filter to exclude"
    )


def test_records_windows_match_coverage(session: Session) -> None:
    """Team records span all team-totals seasons; player records stay scored (F-22)."""
    team_window = team_record_window(session)
    player_window = scored_window(session)
    # Player-record window is the scored era; team-record window is wider/equal
    # (team totals reconstructed back through the unscored era).
    assert player_window <= team_window
    # Team window must cover every season that actually has team scores.
    seasons_with_scores = {
        int(sid)
        for sid in session.execute(
            select(Matchup.season_id).where(Matchup.team_score.is_not(None)).distinct()
        ).scalars()
    }
    assert team_window == seasons_with_scores

    book = records_book(session)
    assert set(book["scored_era"]) == set(seasons_scored(session))
    # Every scored year is inside the (wider) team-record era.
    assert set(book["scored_era"]) <= set(book["team_record_era"])


def test_dst_flag_consistent_with_scored_def_rows(session: Session) -> None:
    """``dst_scoring_complete`` ⇔ every scored season has scored DEF rows (F-48)."""
    expected = bool(seasons_scored(session)) and set(seasons_scored(session)) <= set(
        seasons_with_dst_scored(session)
    )
    assert dst_scoring_complete(session) is expected


def test_coverage_payload_shape(session: Session) -> None:
    """``compute_coverage`` returns the documented keys with sane types/relationships."""
    cov = compute_coverage(session)
    assert set(cov) == {
        "seasons_present",
        "seasons_scored",
        "scored_year_min",
        "scored_year_max",
        "reconstruction_complete",
        "availability_current_season_only",
        "dst_scoring_complete",
    }
    assert cov["seasons_present"] == sorted(cov["seasons_present"])  # type: ignore[arg-type]
    assert cov["seasons_scored"] == sorted(cov["seasons_scored"])  # type: ignore[arg-type]
    assert cov["scored_year_min"] == seasons_scored(session)[0]
    assert cov["scored_year_max"] == seasons_scored(session)[-1]
    assert isinstance(cov["reconstruction_complete"], bool)
    assert isinstance(cov["dst_scoring_complete"], bool)
