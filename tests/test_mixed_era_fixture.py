"""The mixed-era fixture builder (Sleeper D0) produces every scenario `01` §8 asks for."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries
from sqlalchemy.orm import Session

from ff_dashboard.engine import create_readonly_engine
from tests.sleeper_fixture import COMMISSIONER_TX_ID, SHARED_OWNERS, SLEEPER_YEAR

if TYPE_CHECKING:
    from pathlib import Path

LEGACY_TABLES = (
    "seasons",
    "teams",
    "matchups",
    "team_rosters",
    "transactions",
    "player_stats_scored",
)


def _one(db: Path, sql: str) -> Any:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return c.execute(sql).fetchone()[0]
    finally:
        c.close()


def _sleeper(db: Path, sql: str) -> Any:
    return _one(
        db, sql.replace("{S}", f"(SELECT season_id FROM seasons WHERE year = {SLEEPER_YEAR})")
    )


def test_sleeper_season_is_loaded(mixed_era_db_path: Path) -> None:
    assert (
        _one(mixed_era_db_path, f"SELECT platform FROM seasons WHERE year = {SLEEPER_YEAR}")
        == "sleeper"
    )
    assert _sleeper(mixed_era_db_path, "SELECT count(*) FROM teams WHERE season_id = {S}") == 12
    assert _sleeper(mixed_era_db_path, "SELECT count(*) FROM matchups WHERE season_id = {S}") > 0


def test_owners_are_shared_across_eras(mixed_era_db_path: Path) -> None:
    names = ",".join(f"'{n}'" for n in SHARED_OWNERS)
    shared = _sleeper(
        mixed_era_db_path,
        "SELECT count(DISTINCT o.owner_id) FROM owners o JOIN teams t ON t.owner_id = o.owner_id"
        f" WHERE t.season_id = {{S}} AND o.display_name IN ({names})"
        " AND EXISTS (SELECT 1 FROM teams l JOIN seasons s USING (season_id)"
        "  WHERE l.owner_id = o.owner_id AND s.platform = 'nfl_com')",
    )
    assert shared == len(SHARED_OWNERS)


def test_section8_scenarios_are_present(mixed_era_db_path: Path) -> None:
    db = mixed_era_db_path
    assert (
        _sleeper(
            db,
            "SELECT count(*) FROM teams WHERE season_id = {S} AND extra_data LIKE '%co_owner_user_ids%'",
        )
        >= 1
    )
    assert (
        _sleeper(
            db,
            f"SELECT count(*) FROM transactions WHERE season_id = {{S}} AND platform_transaction_id = '{COMMISSIONER_TX_ID}' AND extra_data LIKE '%by_commissioner%'",
        )
        >= 1
    )
    assert (
        _sleeper(
            db, "SELECT count(*) FROM transactions WHERE season_id = {S} AND status = 'failed'"
        )
        >= 1
    )
    assert (
        _sleeper(
            db,
            "SELECT count(*) FROM transactions WHERE season_id = {S} AND transaction_type = 'trade' AND player_id IS NULL",
        )
        >= 1
    )
    assert _one(db, "SELECT count(*) FROM traded_picks") >= 1
    assert _sleeper(db, "SELECT count(*) FROM playoff_brackets WHERE season_id = {S}") >= 1
    # A Sleeper user without a team name gets the canonical "<owner>'s Team" fallback (S5-D5).
    assert (
        _sleeper(
            db, "SELECT count(*) FROM teams WHERE season_id = {S} AND team_name LIKE '%''s Team%'"
        )
        >= 1
    )
    # Provisional weeks: live scores, no result yet (`00` §4).
    assert (
        _sleeper(db, "SELECT count(*) FROM matchups WHERE season_id = {S} AND is_win IS NULL") >= 1
    )


def test_each_era_has_a_capability_gap(mixed_era_db_path: Path) -> None:
    eng = create_readonly_engine(f"sqlite:///{mixed_era_db_path}")
    try:
        with Session(eng) as s:
            legacy = _one(
                mixed_era_db_path, "SELECT min(season_id) FROM seasons WHERE platform = 'nfl_com'"
            )
            sleeper = _one(
                mixed_era_db_path, f"SELECT season_id FROM seasons WHERE year = {SLEEPER_YEAR}"
            )
            for sid in (legacy, sleeper):
                states = {c.state for c in queries.season_capabilities(s, sid).values()}
                assert "not_on_platform" in states, sid
    finally:
        eng.dispose()


def test_legacy_rows_are_untouched_by_the_build(
    fixture_db_path: Path, mixed_era_db_path: Path
) -> None:
    for table in LEGACY_TABLES:
        sql = (
            f"SELECT count(*) FROM {table}"
            if table == "seasons"
            else f"SELECT count(*) FROM {table} WHERE season_id IN (SELECT season_id FROM seasons WHERE platform = 'nfl_com')"
        )
        if table == "team_rosters":
            sql = "SELECT count(*) FROM team_rosters WHERE season_year < 2026"
        legacy = _one(fixture_db_path, sql)
        mixed = _one(mixed_era_db_path, sql) - (1 if table == "seasons" else 0)
        assert mixed == legacy, table
