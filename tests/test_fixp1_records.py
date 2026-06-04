"""fix-P1 / F-22 — records era split (team totals 2010-2025 vs scored 2016-2025)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.records import records_book, scored_window, team_record_window
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_windows_differ(session: Session) -> None:
    # The team-record window includes the unscored 2015 season; the scored window
    # does not.
    team_ids = team_record_window(session)
    scored_ids = scored_window(session)
    assert KNOWN["season_id"][2015] in team_ids
    assert KNOWN["season_id"][2015] not in scored_ids
    assert scored_ids < team_ids


def test_pre_2016_game_can_take_a_record(session: Session) -> None:
    book = records_book(session)
    # Iceman's 50.0 in the 2015 consolation game is the all-time lowest team score.
    low = book["lowest_team_score"]
    assert low["available"] is True
    assert low["value"] == 50.0
    assert low["season_year"] == 2015  # a pre-2016 season holds the record


def test_pinned_team_records_unchanged_by_split(session: Session) -> None:
    book = records_book(session)
    # The era split must not move records that legitimately belong to scored years.
    assert book["highest_team_score"]["value"] == KNOWN["highest_team_score"]  # 160.4 (2017)
    assert book["biggest_blowout"]["value"] == KNOWN["biggest_blowout_margin"]  # 70.0 (2016)
    assert book["narrowest_win"]["value"] == 1.0  # 2016


def test_player_records_stay_scoped_to_scored_era(session: Session) -> None:
    book = records_book(session)
    assert book["scored_era"] == KNOWN["seasons_scored"]  # [2016, 2017]
    assert 2015 in book["team_record_era"]
    assert book["best_player_week"]["season_year"] in {2016, 2017}
