"""Unit tests for the /seasons/ setting-change tiered classifier.

These exercise the pure classification / phase / aggregation logic against the
locked Decisions log (no DB). DB-backed wiring (nothing-dropped, routine bucket,
in-season marker, STATE absorb-vs-hedge) is covered in test_league_history.py.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from ff_dashboard.analytics.league_changes import (
    RawSettingChange,
    _emit_group,
    _emit_individual,
    classify,
    phase_for,
)


def _raw(
    desc: str, year: int = 2016, month: int = 7, day: int = 1, actor: str = "Dan"
) -> RawSettingChange:
    return RawSettingChange(
        season_id=0,
        year=year,
        executed_at=datetime(year, month, day, 12, 0, 0),
        description=desc,
        actor=actor,
    )


@pytest.mark.parametrize(
    ("desc", "canonical", "tier", "treatment"),
    [
        (
            "harry changed Playoff Settings from 'Weeks 15 & 16 - 4 teams' to 'Weeks 15, 16 & 17 - 6 teams'",
            "playoff_settings",
            "T1",
            "PASS",
        ),
        ("harry updated playoff teams", "playoff_teams", "T2", "MISSING"),
        ("harry updated roster positions", "roster_positions", "T1", "STATE"),
        ("harry updated scoring settings", "scoring_settings", "T1", "STATE"),
        (
            "harry changed Trade Reject Time from '2 days' to '1 day'",
            "trade_reject_time",
            "T2",
            "PASS",
        ),
        ("harry changed Waiver Period from '2 days' to '1 day'", "waiver_period", "T2", "PASS"),
        ("harry changed Fee for Joining League from '100.00' to '125.00'", "fee", "T2", "PASS"),
        (
            "harry changed Post Draft Players from 'Follow Waiver Rules' to 'Free Agents'",
            "post_draft_players",
            "T2",
            "PASS",
        ),
        (
            "harry changed Undroppable List from 'NFL.com Fantasy' to 'None'",
            "undroppable_list",
            "T2",
            "PASS",
        ),
        ("Jeff updated the Draft Board", "draft_board", "T2", "MISSING"),
        (
            "Dan changed Ice Station Zebra Waiver Budget from '39' to '76'",
            "waiver_budget_team",
            "T2",
            "MISSING",
        ),
        ("harry changed Draft Time to 'Aug 17, 2011 7:30pm PDT'", "draft_time", "T3", "COLLAPSE"),
        ("harry changed Draft Type from 'offline' to 'live'", "draft_type", "T3", "COLLAPSE"),
        ("harry changed Draft Order from 'snake' to 'custom'", "draft_order", "T3", "COLLAPSE"),
        ("harry randomized Custom Draft Order", "draft_order_randomized", "T3", "COLLAPSE"),
        ("scott Reset the draft", "draft_reset", "T3", "COLLAPSE"),
        (
            "harry changed Ill Edit Story Permission from 'No' to 'Yes'",
            "edit_story_permission",
            "T3",
            "COLLAPSE",
        ),
        ("harry IAMTHEOMEN Player Adds Count", "player_adds_count", "T3", "COLLAPSE"),
        (
            "harry changed Standings Tiebreaker from 'Head to Head Record' to 'Points For'",
            "standings_tiebreaker",
            "T2",
            "PASS",
        ),
    ],
)
def test_classify_detects_and_tiers(desc: str, canonical: str, tier: str, treatment: str) -> None:
    c = classify(_raw(desc))
    assert c.canonical_type == canonical
    assert c.tier == tier
    assert c.treatment == treatment


def test_classify_splits() -> None:
    # Trade review: pre-2012 substantive transition (T2) vs later re-confirm (T3).
    early = classify(
        _raw("harry changed Trade Review Type from 'League Manager Veto' to 'No Review'", year=2011)
    )
    late = classify(
        _raw(
            "Rob changed Trade Review Type from 'League Votes (by team managers)' to 'No Review'",
            year=2025,
        )
    )
    assert (early.tier, early.treatment) == ("T2", "PASS")
    assert (late.tier, late.treatment) == ("T3", "COLLAPSE")

    # Trade deadline: first-ever (No Deadline -> date) is T1; net-zero shuffle is T3.
    first = classify(
        _raw("Jeff changed Trade Deadline from 'No Deadline' to 'November 15, 2019'", year=2019)
    )
    shuffle = classify(
        _raw(
            "harry changed Trade Deadline from 'November 18, 2011' to 'November 25, 2011'",
            year=2011,
        )
    )
    assert first.tier == "T1"
    assert shuffle.tier == "T3"

    # Time per pick: steady-state era (T2) vs reverted blip (T3).
    era = classify(_raw("Chris changed Time Per Pick from '300' to '120'", year=2020))
    blip = classify(_raw("Chris changed Time Per Pick from '15' to '300'", year=2020))
    assert era.tier == "T2"
    assert blip.tier == "T3"


def test_per_team_budget_change_names_the_team() -> None:
    # The per-team FAAB budget event has no team_id — the only link is the team
    # name in the description. The rendered title and summary must surface it so
    # the Timeline doesn't show a generic "a team's budget" for an anomalous,
    # team-specific event (here: Ice Station Zebra's 2022 refund).
    c = classify(_raw("Dan changed Ice Station Zebra Waiver Budget from '39' to '76'", year=2022))
    detail = _emit_individual(c)
    assert "Ice Station Zebra" in detail["title"]
    assert "Ice Station Zebra" in detail["summary"]
    assert "39→76" in detail["summary"]


def test_league_wide_budget_default_has_no_team_target() -> None:
    # The league default ("changed Waiver Budget to '100'") names no team and must
    # not be mis-parsed into a phantom target.
    from ff_dashboard.analytics.league_changes import _budget_target

    assert _budget_target("Chris changed Waiver Budget to '100'") is None
    assert _budget_target("Dan changed Ice Station Zebra Waiver Budget from '39' to '76'") == (
        "Ice Station Zebra"
    )


def test_classify_reattributes_adjusted_points() -> None:
    c = classify(
        _raw(
            "Dan changed Smokin Doubs Adjusted Pts For Week 17 from '0.00' to '55.26'",
            year=2022,
            month=1,
            day=16,
        )
    )
    assert c.canonical_type == "adjusted_points"
    assert c.display_year == 2021  # filed 2022, belongs to the 2021 championship week
    assert c.phase == "off_season"  # Jan 16 is before the 2022 kickoff (oracle-consistent)
    assert c.tier == "T1"


def test_catch_all_degrades_to_t3() -> None:
    c = classify(_raw("harry invented a brand new setting nobody has seen"))
    assert c.canonical_type == "other"
    assert c.tier == "T3"
    assert c.treatment == "HEDGE"


# --- phase oracle: each season's last off-season + first in-season row from the
#     267-row chronological list in the inventory. Regression for WEEK1_KICKOFF.
@pytest.mark.parametrize(
    ("year", "month", "day", "expected"),
    [
        (2010, 8, 6, "off_season"),
        (2010, 9, 20, "in_season"),
        (2011, 9, 1, "off_season"),
        (2011, 9, 12, "in_season"),
        (2012, 8, 20, "off_season"),
        (2012, 9, 26, "in_season"),
        (2013, 8, 16, "off_season"),
        (2013, 9, 30, "in_season"),
        (2014, 9, 2, "off_season"),
        (2014, 10, 9, "in_season"),
        (2015, 8, 17, "off_season"),
        (2015, 12, 9, "in_season"),
        (2016, 8, 24, "off_season"),
        (2016, 9, 30, "in_season"),
        (2017, 9, 3, "off_season"),
        (2017, 12, 5, "in_season"),
        (2018, 9, 2, "off_season"),
        (2018, 9, 14, "in_season"),
        (2019, 9, 3, "off_season"),
        (2019, 11, 3, "in_season"),
        (2020, 9, 4, "off_season"),
        (2021, 8, 29, "off_season"),
        (2022, 8, 6, "off_season"),
        (2022, 9, 16, "in_season"),
        (2023, 8, 20, "off_season"),
        (2023, 11, 14, "in_season"),
        (2024, 8, 29, "off_season"),
        (2024, 9, 17, "in_season"),
        (2025, 9, 1, "off_season"),
        (2025, 9, 28, "in_season"),
    ],
)
def test_phase_oracle(year: int, month: int, day: int, expected: str) -> None:
    assert phase_for(datetime(year, month, day), year) == expected


# --- aggregation ----------------------------------------------------------
def test_emit_group_faab_merge() -> None:
    items = [
        classify(
            _raw(
                "Chris changed Waiver Type from 'Resets to Inverse Standings Order' to 'Waiver Budget'",
                year=2021,
                month=8,
                day=27,
            )
        ),
        classify(_raw("Chris changed Waiver Budget to '100'", year=2021, month=8, day=27)),
    ]
    event, leftovers = _emit_group("faab-2021", items)
    assert leftovers == []
    assert event is not None
    assert event["tier"] == "T1"
    assert "FAAB" in event["summary"] and "$100" in event["summary"]
    assert len(event["members"]) == 2


def test_emit_group_division_realignment_counts() -> None:
    items = [
        classify(
            _raw(f"harry changed Team{i}'s Division from '1' to '2'", year=2011, month=8, day=6)
        )
        for i in range(12)
    ]
    event, leftovers = _emit_group("div-2011-2011-08-06", items)
    assert leftovers == []
    assert event["tier"] == "T1"
    assert "12 teams" in event["summary"]
    assert len(event["members"]) == 12


def test_emit_group_waiver_priority_small_swap_falls_through() -> None:
    items = [
        classify(_raw("Dave changed A Waiver Priority from '5' to '6'", year=2017, month=9, day=3)),
        classify(_raw("Dave changed B Waiver Priority from '6' to '5'", year=2017, month=9, day=3)),
    ]
    event, leftovers = _emit_group("wpri-2017-2017-09-03", items)
    assert event is None  # trivial 2-team swap -> routine bucket, not an elevated event
    assert len(leftovers) == 2


def test_emit_group_commish_filters_co_manager_noise() -> None:
    items = [
        classify(
            _raw("Dave assigned League Management Privileges to Jeff.", year=2018, month=5, day=13)
        ),
        classify(
            _raw("Jeff removed League Management Privileges from Dave.", year=2018, month=5, day=13)
        ),
        classify(
            _raw("Jeff assigned League Management Privileges to harry.", year=2018, month=5, day=18)
        ),
        classify(
            _raw(
                "Jeff removed League Management Privileges from harry.", year=2018, month=8, day=25
            )
        ),
    ]
    event, _ = _emit_group("commish-2018", items)
    assert event is not None
    # harry was assigned-then-removed same year -> noise, excluded from the signal.
    assert "harry" not in event["summary"]
    assert "Jeff" in event["summary"]  # net assignment
    assert len(event["members"]) == 4  # nothing dropped — all rows kept as members
