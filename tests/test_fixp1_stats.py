"""fix-P1 / F-31 — week-capped season totals (no NFL post-season inflation)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Season

from ff_dashboard.analytics.stats import season_totals
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
    # Jefferson (58.0, all within the fantasy schedule) is still the leader.
    assert rows[0]["name_full"] == "Justin Jefferson"
    assert rows[0]["total_points"] == 58.0


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
    per-week team (cmc, jjet) fall back to that snapshot.
    """
    s = session.get(Season, KNOWN["season_id"][2017])
    assert s is not None
    rows = season_totals(session, s)
    by_name = {r["name_full"]: r["nfl_team"] for r in rows}
    assert by_name["Relocation Reggie"] == "OAK"
    assert by_name["Christian McCaffrey"] == "SF"
    assert by_name["Justin Jefferson"] == "MIN"
