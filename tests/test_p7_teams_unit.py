"""P7 — team-page analytics unit tests against the fixture's known answers.

The 2017 season is the workhorse here: Iceman goes 2-0 (top seed) while Maverick
goes 1-1 but is the champion — so these tests prove the team header reads the
standings correctly *and* that champion != standings leader.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import TeamRoster
from sqlalchemy import func, select

from ff_dashboard.analytics.teams import (
    _BUDGET_ADJUST_RE,
    _faab_bid,
    _faab_budget_weeks,
    _norm_name,
    team_faab_budget,
    team_overview,
    team_roster,
    team_schedule,
    team_scoring_trend,
    team_transactions,
)
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --- Overview --------------------------------------------------------------


def test_overview_reads_standings_for_top_seed(session: Session) -> None:
    ice_2017 = KNOWN["team_id"][(2017, "ice")]
    data = team_overview(session, ice_2017)
    assert data is not None
    assert data["season_year"] == 2017
    assert data["owner_name"] == "Iceman"
    assert (data["wins"], data["losses"], data["ties"]) == (2, 0, 0)
    assert data["points_for"] == 235.0
    assert data["points_against"] == 225.0
    assert data["rank"] == 1
    assert data["rank_basis"] == "computed"  # 2017 teams carry no final_rank
    assert data["is_champion"] is False
    assert data["is_scored"] is True


def test_overview_champion_is_not_the_standings_leader(session: Session) -> None:
    mav_2017 = KNOWN["team_id"][(2017, "mav")]
    data = team_overview(session, mav_2017)
    assert data is not None
    assert data["is_champion"] is True
    assert (data["wins"], data["losses"]) == (1, 1)
    assert data["rank"] != 1  # champion was not the regular-season #1 seed


def test_overview_unknown_team_is_none(session: Session) -> None:
    assert team_overview(session, 999999) is None


# --- Roster ----------------------------------------------------------------


def test_roster_latest_week_with_scored_points(session: Session) -> None:
    ice_2017 = KNOWN["team_id"][(2017, "ice")]
    data = team_roster(session, ice_2017, week=1)
    assert data is not None
    assert data["week"] == 1
    assert data["is_scored"] is True
    assert len(data["players"]) == 13  # the hand-authored box lineup
    qb1 = next(p for p in data["players"] if p["player_name"] == "Ice QB One")
    assert qb1["league_points"] == 24.0
    assert qb1["is_starter"] is True


def test_roster_scored_dst_carries_points(session: Session) -> None:
    # DST is scored end-to-end, so Iceman's DEF starter shows real league points.
    ice_2017 = KNOWN["team_id"][(2017, "ice")]
    data = team_roster(session, ice_2017, week=1)
    assert data is not None
    dst = next(p for p in data["players"] if p["position"] == "DEF")
    assert dst["league_points"] == KNOWN["box_dst_points"]  # 9.0


def test_roster_missing_dst_points_are_null_not_zero(session: Session) -> None:
    # A DEF row that is genuinely absent stays null, never a fake 0. Goose's
    # 2017 wk1 DST has no scored row (the per-row gap that survives DST scoring).
    goose_2017 = KNOWN["team_id"][(2017, "goose")]
    data = team_roster(session, goose_2017, week=1)
    assert data is not None
    dst = next(p for p in data["players"] if p["position"] == "DEF")
    assert dst["league_points"] is None  # never a fake 0


def test_roster_uses_box_score_zero_context(session: Session) -> None:
    goose_2017 = KNOWN["team_id"][(2017, "goose")]
    data = team_roster(session, goose_2017, week=1)
    assert data is not None
    rows = {p["player_name"]: p for p in data["players"]}

    dnp = rows["No Stat Bench Guy"]
    assert dnp["league_points"] == 0.0
    assert dnp["zero_reason"] == "did_not_play"

    bye = rows["Bye Week Guy"]
    assert bye["league_points"] == 0.0
    assert bye["zero_reason"] == "bye"

    mismatch = rows["Mismatch Guy"]
    assert mismatch["league_points"] == 0.0
    assert mismatch["zero_reason"] == "unexpected"
    assert mismatch["zero_detail"] is not None

    dst = rows["Goose D/ST"]
    assert dst["league_points"] is None
    assert dst["zero_reason"] is None


def test_roster_unknown_team_is_none(session: Session) -> None:
    assert team_roster(session, 999999, week=1) is None


def test_roster_pads_short_week_with_empty_slots(session: Session) -> None:
    # Snapshots record the week-end roster, so a week where players were dropped
    # and not replaced carries fewer rows. That week should pad up to the team's
    # usual size with dashed empty slots rather than shrinking. (The fixture has
    # one team that is full one week and nearly empty the next.)
    counts: dict[int, dict[int, int]] = {}
    for tid, wk, n in session.execute(
        select(TeamRoster.team_id, TeamRoster.week, func.count())
        .where(TeamRoster.week > 0)
        .group_by(TeamRoster.team_id, TeamRoster.week)
    ).all():
        counts.setdefault(int(tid), {})[int(wk)] = int(n)

    team_id, weeks = next(
        (tid, wks)
        for tid, wks in counts.items()
        if len(wks) > 1 and min(wks.values()) < max(wks.values())
    )
    expected = max(weeks.values())
    short_week = min(weeks, key=lambda w: weeks[w])

    data = team_roster(session, team_id, week=short_week)
    assert data is not None
    assert len(data["players"]) == expected  # padded to the team's usual size
    empties = [p for p in data["players"] if p["is_empty"]]
    assert len(empties) == expected - weeks[short_week]
    assert all(p["player_name"] is None and p["league_points"] is None for p in empties)
    assert any(p["is_empty"] is False for p in data["players"])  # real players remain


# --- Schedule --------------------------------------------------------------


def test_schedule_results_and_deep_links(session: Session) -> None:
    ice_2017 = KNOWN["team_id"][(2017, "ice")]
    data = team_schedule(session, ice_2017)
    assert data is not None
    assert len(data["games"]) == 2
    wk1 = next(g for g in data["games"] if g["week"] == 1)
    assert wk1["result"] == "W"
    assert wk1["team_score"] == 130.0
    assert wk1["opponent_score"] == 125.0
    assert wk1["margin"] == 5.0
    assert wk1["opponent_owner_name"] == "Goose"
    assert wk1["matchup_id"] == KNOWN["matchup_id"][(2017, 1, "ice")]


# --- Scoring trend ---------------------------------------------------------


def test_scoring_trend_vs_league_average(session: Session) -> None:
    ice_2017 = KNOWN["team_id"][(2017, "ice")]
    data = team_scoring_trend(session, ice_2017)
    assert data is not None
    pts = {p["week"]: p for p in data["points"]}
    # wk1 league avg = (160.4 + 120 + 130 + 125) / 4 = 133.85
    assert pts[1]["team_score"] == 130.0
    assert pts[1]["league_avg"] == 133.85
    # wk2 league avg = (105 + 100 + 140 + 110) / 4 = 113.75
    assert pts[2]["team_score"] == 105.0
    assert pts[2]["league_avg"] == 113.75


def test_scoring_trend_works_for_unscored_season(session: Session) -> None:
    # 2015 has no player-level scoring, but team scores exist — the trend must
    # still plot (the gap is about player stats, not team totals).
    mav_2015 = KNOWN["team_id"][(2015, "mav")]
    data = team_scoring_trend(session, mav_2015)
    assert data is not None
    assert data["is_scored"] is False
    assert all(p["team_score"] is not None for p in data["points"])


# --- Transactions ----------------------------------------------------------


def test_transactions_are_acquisitions_only(session: Session) -> None:
    # The team-transactions feed is scoped to roster acquisitions; the fixture's
    # `lineup_change` (a start/sit move) must be filtered out.
    ice_2017 = KNOWN["team_id"][(2017, "ice")]
    data = team_transactions(session, ice_2017)
    assert data is not None
    assert [t["transaction_type"] for t in data["transactions"]] == ["waiver_add"]
    assert all(t["transaction_type"] != "lineup_change" for t in data["transactions"])

    waiver = data["transactions"][0]
    assert waiver["executed_at"] == "2017-09-12T10:15:00"
    assert waiver["effective_week"] == 2
    assert waiver["player_name"] == "Justin Jefferson"
    assert waiver["direction"] == "in"
    assert waiver["waiver_priority_used"] == 4
    assert waiver["faab_bid"] is None
    assert waiver["notes"] == "Iceman"


# --- FAAB bid extraction ---------------------------------------------------


def test_faab_bid_reads_zero_as_a_real_bid() -> None:
    # A $0 bid is a legitimate free waiver claim, not a missing bid. The prior
    # ``or``-chain collapsed 0 to None; presence-based lookup must keep it.
    assert _faab_bid({"faab_bid": 0}) == 0.0
    assert _faab_bid({"faab_bid": 10}) == 10.0
    assert _faab_bid({"faab_bid": 100.0}) == 100.0


def test_faab_bid_absent_or_null_is_none() -> None:
    # Pre-FAAB rows (no key) and explicit-null keys both mean "no bid recorded".
    assert _faab_bid(None) is None
    assert _faab_bid({}) is None
    assert _faab_bid({"snapshot_kind": "history"}) is None
    assert _faab_bid({"faab_bid": None}) is None


def test_faab_bid_falls_back_to_legacy_keys() -> None:
    # Only when the canonical key is absent; a non-numeric value is skipped.
    assert _faab_bid({"faab": 7}) == 7.0
    assert _faab_bid({"bid": 3}) == 3.0
    assert _faab_bid({"faab_bid": "not-a-number"}) is None
    assert _faab_bid({"faab_bid": None, "faab": 5}) == 5.0


# --- FAAB remaining-budget -------------------------------------------------


def test_budget_adjust_regex_parses_team_and_delta() -> None:
    # The per-team budget event has no team_id; the team + before/after come from
    # the description text. The league-wide default (no from/to) must NOT match.
    m = _BUDGET_ADJUST_RE.search("Dan changed Ice Station Zebra Waiver Budget from '39' to '76'")
    assert m is not None
    assert _norm_name(m.group("team")) == _norm_name("Ice Station Zebra")
    assert float(m.group("after")) - float(m.group("before")) == 37.0
    assert _BUDGET_ADJUST_RE.search("Chris changed Waiver Budget to '100'") is None


def test_faab_budget_weeks_flat_budget_no_credits() -> None:
    # remaining = 100 - running spend; only active weeks emit a row, balance carries.
    weeks, total, final = _faab_budget_weeks({1: 10.0, 3: 5.0}, {}, 100.0)
    assert [(w["week"], w["spent"], w["remaining"]) for w in weeks] == [
        (1, 10.0, 90.0),
        (3, 5.0, 85.0),
    ]
    assert (total, final) == (15.0, 85.0)
    assert all(w["adjustment"] is None for w in weeks)


def test_faab_budget_weeks_mid_season_credit_refund() -> None:
    # The Ice Station Zebra 2022 shape: $61 spent in wk2 plus a +$37 refund the
    # same week nets remaining to $76; a timestamped credit, not a flat total.
    weeks, total, final = _faab_budget_weeks({2: 61.0, 9: 12.0}, {2: 37.0}, 100.0)
    by_week = {w["week"]: w for w in weeks}
    assert by_week[2]["budget"] == 137.0
    assert by_week[2]["remaining"] == 76.0
    assert by_week[2]["adjustment"] == 37.0
    assert "37" in by_week[2]["note"]
    assert by_week[9]["remaining"] == 64.0  # 137 - 73
    assert (total, final) == (73.0, 64.0)


def test_faab_budget_weeks_guard_allows_overspend_to_show_negative() -> None:
    # Without an attributable credit, overspend yields a negative remaining the UI
    # renders as a gap (never a fake 0). The analytic returns the true figure.
    weeks, _total, final = _faab_budget_weeks({5: 130.0}, {}, 100.0)
    assert weeks[0]["remaining"] == -30.0
    assert final == -30.0


def test_team_faab_budget_derives_weekly_remaining(session: Session) -> None:
    # Goose 2017 is FAAB-era (its waiver claims carry faab_bid): $10, a $0 free
    # claim, then $5 -> remaining 90, 90, 85; a $0 week is real, not missing.
    goose_2017 = KNOWN["team_id"][(2017, "goose")]
    data = team_faab_budget(session, goose_2017)
    assert data is not None
    assert data["is_faab_era"] is True
    assert data["available"] is True
    assert data["season_budget"] == 100.0
    assert [(w["week"], w["spent"], w["remaining"]) for w in data["weeks"]] == [
        (1, 10.0, 90.0),
        (2, 0.0, 90.0),
        (3, 5.0, 85.0),
    ]
    assert (data["total_spent"], data["final_remaining"]) == (15.0, 85.0)


def test_team_faab_budget_pre_faab_season_is_not_applicable(session: Session) -> None:
    # 2016 has no captured bids -> waiver-priority era. Not a gap, not zeros:
    # is_faab_era=False so the UI simply doesn't show a budget view.
    mav_2016 = KNOWN["team_id"][(2016, "mav")]
    data = team_faab_budget(session, mav_2016)
    assert data is not None
    assert data["is_faab_era"] is False
    assert data["available"] is False
    assert data["season_budget"] is None
    assert data["weeks"] == []


def test_team_faab_budget_unknown_team_is_none(session: Session) -> None:
    assert team_faab_budget(session, 999999) is None
