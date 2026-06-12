"""fix-P1 / F-22 - records era split is data-driven."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.records import records_book, scored_window, team_record_window
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_windows_follow_coverage(session: Session) -> None:
    # The fixture keeps one generic unscored season with team totals; the windows
    # differ because of coverage, not because of a hardcoded calendar era.
    team_ids = team_record_window(session)
    scored_ids = scored_window(session)
    assert KNOWN["season_id"][2015] in team_ids
    assert KNOWN["season_id"][2015] not in scored_ids
    assert scored_ids < team_ids


def test_unscored_team_total_season_can_take_a_team_record(session: Session) -> None:
    book = records_book(session)
    # Iceman's 50.0 in the 2015 consolation game is the all-time lowest team score.
    low = book["lowest_team_score"]
    assert low["available"] is True
    assert low["value"] == 50.0
    assert low["season_year"] == 2015  # team records are not gated by player scoring


def test_pinned_team_records_unchanged_by_split(session: Session) -> None:
    book = records_book(session)
    # The era split must not move records that legitimately belong to scored years.
    assert book["highest_team_score"]["value"] == KNOWN["highest_team_score"]  # 160.4 (2017)
    assert book["biggest_blowout"]["value"] == KNOWN["biggest_blowout_margin"]  # 70.0 (2016)
    assert book["narrowest_win"]["value"] == 1.0  # 2016


def test_player_records_stay_scoped_to_scored_era(session: Session) -> None:
    book = records_book(session)
    assert book["scored_era"] == KNOWN["seasons_scored"]
    assert 2015 in book["team_record_era"]
    assert book["best_player_week"]["season_year"] in set(KNOWN["seasons_scored"])
