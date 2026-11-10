"""Sleeper D2: source-neutral points (plan sleeper-d2-source-neutral-points)."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from ff_pipeline.repository.models import (
    Matchup,
    PlayerStatsRaw,
    PlayerStatsScored,
    Season,
    TeamRoster,
)
from sqlalchemy import Float, and_, cast, create_engine, func, select
from sqlalchemy.orm import Session

from ff_dashboard.analytics.scoring import (
    authoritative_week_points,
    official_points,
    official_points_from_extra,
)
from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine
from tests.sleeper_fixture import SLEEPER_YEAR

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _session(path: Path) -> Iterator[Session]:
    eng = create_readonly_engine(f"sqlite:///{path}")
    with Session(eng) as s:
        yield s
    eng.dispose()


@pytest.fixture
def legacy_session(fixture_db_path: Path) -> Iterator[Session]:
    yield from _session(fixture_db_path)


@pytest.fixture
def mixed_session(mixed_era_db_path: Path) -> Iterator[Session]:
    yield from _session(mixed_era_db_path)


def _old_vs_new(session: Session, *, legacy_only: bool) -> list[tuple[Any, Any]]:
    """(old NFL.com-only coalesce, new authoritative) for every roster row."""
    old = func.coalesce(
        cast(func.json_extract(TeamRoster.extra_data, "$.nfl_com_points"), Float),
        PlayerStatsScored.total_points,
    )
    q = (
        select(old, authoritative_week_points())
        .select_from(TeamRoster)
        .join(Season, Season.year == TeamRoster.season_year)
        .outerjoin(
            PlayerStatsScored,
            and_(
                PlayerStatsScored.player_id == TeamRoster.player_id,
                PlayerStatsScored.season_id == Season.season_id,
                PlayerStatsScored.week == TeamRoster.week,
            ),
        )
    )
    if legacy_only:
        q = q.where(Season.platform.is_(None) | (Season.platform == "nfl_com"))
    return [(r[0], r[1]) for r in session.execute(q)]


# --- legacy parity ----------------------------------------------------------------------------


@pytest.mark.parametrize("which", ["legacy_session", "mixed_session"])
def test_authoritative_equals_old_expression_on_every_legacy_row(
    which: str, request: pytest.FixtureRequest
) -> None:
    session: Session = request.getfixturevalue(which)
    rows = _old_vs_new(session, legacy_only=True)
    assert rows
    assert [r for r in rows if r[0] != r[1]] == []


# --- the dict-side mirror agrees with the upstream SQL helper ---------------------------------


def test_official_points_from_extra_matches_upstream_expr(mixed_session: Session) -> None:
    rows = mixed_session.execute(select(TeamRoster.extra_data, official_points())).all()
    assert rows
    mismatches = [(e, sql) for e, sql in rows if official_points_from_extra(e) != sql]
    assert mismatches == []
    # The mixed DB holds both platforms' keys, so both branches are exercised.
    kinds = {k for e, _ in rows if isinstance(e, dict) for k in e}
    assert {"platform_points", "nfl_com_points"} <= kinds


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({"platform_points": 12.5, "nfl_com_points": 3.0}, 12.5),
        ({"nfl_com_points": 3}, 3.0),
        ({"platform_points": 0.0}, 0.0),  # a real zero, not a gap
        ({"platform_points": True, "nfl_com_points": 4.0}, 4.0),
        ({"platform_points": "12"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_official_points_from_extra_precedence(extra: Any, expected: float | None) -> None:
    assert official_points_from_extra(extra) == expected


# --- a Sleeper-era box score shows official points ----------------------------------------------

# The reconstruction is deliberately off by this much, so a box score that read
# player_stats_scored instead of platform_points would fail.
_RECON_OFFSET = 1.25


def _first_sleeper_game(session: Session) -> Matchup:
    return session.execute(
        select(Matchup)
        .join(Season, Season.season_id == Matchup.season_id)
        .where(Season.year == SLEEPER_YEAR, Matchup.opponent_team_id.is_not(None))
        .order_by(Matchup.week, Matchup.matchup_id)
        .limit(1)
    ).scalar_one()


@pytest.fixture(scope="module")
def scored_mixed_db(mixed_era_db_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the mixed-era DB with 2026 marked scored, as the go-live rescore leaves it.

    The upstream Sleeper fixture is loaded without a rescore, so 2026 has no
    ``player_stats_scored`` rows and the box score reports ``season_unscored``. This
    copy adds reconstruction rows for one game's rostered players (test-only writes
    to a temp copy; ``src/`` stays read-only).
    """
    out = tmp_path_factory.mktemp("dzmixed_scored") / "fantasy.db"
    src = sqlite3.connect(f"file:{mixed_era_db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    eng = create_engine(f"sqlite:///{out}", future=True)
    try:
        with Session(eng) as ss:
            m = _first_sleeper_game(ss)
            rows = ss.execute(
                select(TeamRoster.player_id, official_points()).where(
                    TeamRoster.team_id.in_([m.team_id, m.opponent_team_id]),
                    TeamRoster.season_year == SLEEPER_YEAR,
                    TeamRoster.week == m.week,
                )
            ).all()
            for pid, pts in rows:
                raw = PlayerStatsRaw(
                    player_id=pid,
                    season_year=SLEEPER_YEAR,
                    week=m.week,
                    source="d2_test",
                    is_primary=True,
                )
                ss.add(raw)
                ss.flush()
                ss.add(
                    PlayerStatsScored(
                        stat_id=raw.stat_id,
                        season_id=m.season_id,
                        player_id=pid,
                        week=m.week,
                        total_points=(pts or 0.0) + _RECON_OFFSET,
                    )
                )
            ss.commit()
    finally:
        eng.dispose()
    return out


def test_sleeper_box_score_uses_platform_points(scored_mixed_db: Path) -> None:
    eng = create_readonly_engine(f"sqlite:///{scored_mixed_db}")
    try:
        with Session(eng) as s:
            m = _first_sleeper_game(s)
            expected = {
                int(pid): round(float(pts), 2)
                for pid, pts in s.execute(
                    select(TeamRoster.player_id, official_points()).where(
                        TeamRoster.team_id == m.team_id,
                        TeamRoster.week == m.week,
                        TeamRoster.season_year == SLEEPER_YEAR,
                    )
                )
                if pts is not None
            }
        assert expected, "fixture roster rows should carry platform_points"

        app = create_app(eng, cache=AnalyticsCache(), cors_origins=[])
        with TestClient(app) as c:
            r = c.get(f"/v1/matchups/{m.matchup_id}/box-score")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["available"] is True
        side = next(
            t
            for t in (body["home"], body["away"])
            if isinstance(t, dict) and t["team_id"] == m.team_id
        )
        players = [p for p in side["lineup"] if p["player_id"] in expected]
        assert len(players) == len(expected)
        for p in players:
            assert p["available"] is True
            assert p["league_points"] == expected[p["player_id"]]
        # The official starters sum to Sleeper's computed total. This fixture game
        # carries the synthetic commissioner override, so ``team_score`` is
        # ``custom_points`` and the computed total is kept in ``points_official``.
        official_total = (m.extra_data or {}).get("points_official", m.team_score)
        assert side["starter_points"] == pytest.approx(float(official_total), abs=0.05)
    finally:
        eng.dispose()
