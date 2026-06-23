"""Stats leaderboards (``analytics/stats.py``): week-capped season totals (no NFL
post-season inflation, F-31), the bonus-inclusive authoritative score, and the
rostered-ever league-relevance filter (bonus-scoring fidelity)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Season

from ff_dashboard.analytics.stats import season_totals, top_scorers
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_beyond_championship_weeks_excluded(session: Session) -> None:
    s = session.get(Season, KNOWN["season_id"][2017])
    assert s is not None
    rows = season_totals(session, s)
    cmc = next(r for r in rows if r["name_full"] == "Christian McCaffrey")
    # Weeks 1+2 only (22+20); the week-4 post-championship 30.0 is excluded.
    assert cmc["total_points"] == 42.0
    assert cmc["weeks_played"] == 2
    # Jefferson (58.0) is the highest *scored* line but is never rostered, so the
    # rostered-ever filter drops him; McCaffrey leads among league-relevant players.
    assert rows[0]["name_full"] == "Christian McCaffrey"
    assert rows[0]["total_points"] == 42.0


def test_never_rostered_players_excluded(session: Session) -> None:
    """The reconstruction scores the whole NFL; a player nobody ever rostered is
    not a league leaderboard entry — even the season's top *scored* line."""
    s = session.get(Season, KNOWN["season_id"][2017])
    assert s is not None
    names = {r["name_full"] for r in season_totals(session, s)}
    assert "Justin Jefferson" not in names  # 58.0 but never rostered
    assert "Lamar Jackson" not in names  # 35.5 best week but never rostered
    assert "Christian McCaffrey" in names  # rostered → relevant


def test_season_totals_use_authoritative_coalesce(session: Session) -> None:
    """Each week is summed as coalesce(nfl_com_points, total_points): Reggie's
    week-1 NFL.com score (10.0) is used over the reconstruction's 6.0."""
    s = session.get(Season, KNOWN["season_id"][2017])
    assert s is not None
    reggie = next(r for r in season_totals(session, s) if r["name_full"] == "Relocation Reggie")
    # wk1 authoritative 10.0 (not raw 6.0) + wk2 raw 5.0 (no roster row) = 15.0.
    assert reggie["total_points"] == 15.0


def test_position_filter(session: Session) -> None:
    s = session.get(Season, KNOWN["season_id"][2017])
    assert s is not None
    rb_rows = season_totals(session, s, position="RB")
    assert rb_rows
    assert all(r["position"] == "RB" for r in rb_rows)


def test_unscored_season_returns_empty_not_zeros(session: Session) -> None:
    s = session.get(Season, KNOWN["season_id"][2015])
    assert s is not None
    assert season_totals(session, s) == []


def test_season_correct_nfl_team_overrides_current_snapshot(session: Session) -> None:
    """F-54: the leaderboard shows the team a player was on that season.

    Relocation Reggie's 2017 per-week NFL team is stored as nflverse's current
    "LV", which the season-correct read folds back to the 2017-era "OAK" — not
    his current-snapshot ``players.nfl_team`` of "LV". Players with no stored
    per-week team (cmc) fall back to that snapshot.
    """
    s = session.get(Season, KNOWN["season_id"][2017])
    assert s is not None
    rows = season_totals(session, s)
    by_name = {r["name_full"]: r["nfl_team"] for r in rows}
    assert by_name["Relocation Reggie"] == "OAK"
    assert by_name["Christian McCaffrey"] == "SF"


def test_top_scorers_excludes_never_rostered(session: Session) -> None:
    """The per-week leaderboard is league-scoped too: Lamar's 35.5 (the highest
    scored week of 2017) never appears because he was never rostered."""
    rows = top_scorers(session, season_year=2017, week=None, position=None, limit=50)
    names = {r["name_full"] for r in rows}
    assert "Lamar Jackson" not in names
    assert "Justin Jefferson" not in names
    assert "Christian McCaffrey" in names


def test_top_scorers_use_authoritative_coalesce(session: Session) -> None:
    """A week's score is coalesce(nfl_com_points, total_points), applied before the
    order/limit so the bonus can change the ranking (the Vick 58.32→63.32 class)."""
    rows = top_scorers(session, season_year=2017, week=1, position=None, limit=50)
    reggie = next(r for r in rows if r["name_full"] == "Relocation Reggie")
    assert reggie["points"] == 10.0  # authoritative, not the raw 6.0
    # A rostered player without an NFL.com override falls back to the reconstruction.
    cmc = next(r for r in rows if r["name_full"] == "Christian McCaffrey")
    assert cmc["points"] == 22.0
