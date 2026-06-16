"""F-43 — automated data-gap / correctness validation harness.

Cross-checks the dashboard's coverage affordances and computed windows against
the database, asserting the coverage *truths* the 2026-06 in-browser review
found the honesty layer over-claiming (F-16/F-22/F-25/F-31/F-35). The
assertions are **invariants/relationships**, not fixture-specific magic numbers,
so they hold on the real DB too:

* seasons with per-player scoring are discovered from ``player_stats_scored``,
  never from a hardcoded era;
* present-but-unscored seasons can still carry team totals, so team data must not
  read as incomplete just because player scoring is unavailable (F-16/F-31/F-35);
* the player index never leaks never-rostered players (F-25/F-44);
* the records windows match their coverage — team records span all team-totals
  seasons, player records stay in the scored era (F-22);
* the ``dst_scoring_complete`` flag agrees with the scored DEF rows (F-48).

Read-only, against the conftest fixture (one generic unscored gap season plus
scored seasons).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Matchup, Season
from sqlalchemy import func, select

from ff_dashboard.analytics.coverage import (
    compute_coverage,
    compute_coverage_matrix,
    coverage_status_for_projection_week,
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


def _matchups_with_team_scores(session: Session, year: int) -> int:
    """Count matchup rows carrying a real team score for a given season year."""
    return int(
        session.execute(
            select(func.count(Matchup.matchup_id))
            .join(Season, Season.season_id == Matchup.season_id)
            .where(Season.year == year, Matchup.team_score.is_not(None))
        ).scalar_one()
    )


def test_player_scoring_window_is_data_driven(session: Session) -> None:
    """Scored seasons are discovered from rows; scored ⊆ present."""
    scored = seasons_scored(session)
    present = seasons_present(session)
    assert scored, "fixture must have at least one scored season"
    assert set(scored) <= set(present)
    # The fixture keeps one present-but-unscored season so the affordance has a
    # generic gap case to scope to. This must not imply a calendar-era rule.
    assert set(present) - set(scored), "expected a present unscored gap season"


def test_seasons_present_excludes_unplayed_seasons(session: Session) -> None:
    """Coverage reports only seasons with results, never an upcoming empty one.

    The fixture seeds an upcoming season (teams but no games). It has no played
    matchup, so it must be absent from ``seasons_present`` — the coverage view
    must not claim a resultless future season. Data-driven on played games.
    """
    present = set(seasons_present(session))
    all_years = {int(y) for y in session.execute(select(Season.year)).scalars().all()}
    unplayed = all_years - present
    assert unplayed, "fixture must seed an upcoming, not-yet-played season"
    for year in unplayed:
        assert _matchups_with_team_scores(session, year) == 0


def test_team_totals_present_in_unscored_seasons(session: Session) -> None:
    """Present-but-unscored seasons still carry real team scores (F-16/F-35).

    The explicit gap case has matchups with non-null team scores, so team
    results/standings/rosters can be complete even where per-player scoring is
    absent. Labeling those seasons "incomplete" is the over-claim the review
    caught.
    """
    scored = set(seasons_scored(session))
    unscored_present = [y for y in seasons_present(session) if y not in scored]
    assert unscored_present, "fixture must include a present unscored gap season"
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
    # when team totals exist for an unscored season.
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


def test_projection_week_coverage_is_data_driven(session: Session) -> None:
    covered = coverage_status_for_projection_week(session, 2017, 1)
    assert covered["status"] == "present"
    assert covered["reason"] is None
    assert covered["row_count"] == 2

    uncovered = coverage_status_for_projection_week(session, 2017, 2)
    assert uncovered["status"] == "absent"
    assert uncovered["reason"] == "projections_not_captured"
    assert uncovered["row_count"] == 0

    # Hollow rows (projected_points=0 + all-zero stats — Sleeper's pre-coverage
    # shape) must read as absent, not a bogus 0.0 projection. There IS a row, so
    # this guards specifically against counting the hollow row as coverage.
    hollow = coverage_status_for_projection_week(session, 2017, 3)
    assert hollow["status"] == "absent"
    assert hollow["reason"] == "projections_not_captured"
    assert hollow["row_count"] == 1

    # Stats-only rows (projected_points NULL but real projected_stats — the
    # current season's not-yet-scored shape) must read as present.
    stats_only = coverage_status_for_projection_week(session, 2017, 4)
    assert stats_only["status"] == "present"
    assert stats_only["reason"] is None
    assert stats_only["projected_stats_count"] == 1


def test_coverage_matrix_reports_relevance_feeds_and_identity_splits(session: Session) -> None:
    matrix = compute_coverage_matrix(session)
    assert set(matrix) == {"relevance", "feeds", "reason_codes"}
    feeds = matrix["feeds"]
    assert set(feeds) == {
        "rosters",
        "scored_stats",
        "injuries",
        "projections",
        "transactions",
        "availability",
    }

    projections = {
        (cell["season_year"], cell["week"]): cell
        for cell in feeds["projections"]  # type: ignore[index]
    }
    assert projections[(2017, 1)]["status"] == "present"
    assert projections[(2017, 1)]["projected_points_count"] == 2
    assert (2017, 2) not in projections

    relevance = matrix["relevance"]
    assert relevance["total_players"] > relevance["league_rostered_players"]  # type: ignore[index]
    assert relevance["identity_split_candidate_count"] == 1  # type: ignore[index]
    candidate = relevance["identity_split_candidates"][0]  # type: ignore[index]
    assert candidate["name_full"] == "Split Sam"
    assert {m["rostered"] for m in candidate["members"]} == {True, False}
