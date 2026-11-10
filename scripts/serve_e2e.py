"""Boot the BFF against the test fixture database for Playwright e2e.

Playwright's ``webServer`` runs this: it (re)builds the hand-authored fixture
database (the same one the pytest suite uses, via ``tests.conftest``) into
``web/.e2e/fixture.db``, then serves the API *and* the built SPA single-origin
on :8810. e2e specs assert against the fixture's KNOWN answers, so the journeys
are deterministic and never touch the live league DB.

Run indirectly via ``npm run test:e2e`` (or ``make test-e2e``); the SPA must be
built first (``npm run build`` — Playwright's webServer command does this).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT = 8810
#: ``--mixed`` serves the mixed-era fixture (legacy + a Sleeper 2026 season, Sleeper D3) on its
#: own port, so the Sleeper journeys never change the legacy suite's default season.
MIXED_PORT = 8811


def _wait_for_build(timeout: float = 180.0) -> None:
    """The legacy server (:8810) comes up only after ``npm run build``; wait for it, so this
    server mounts the freshly built SPA (Playwright starts both web servers at once)."""
    import time
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise SystemExit("legacy e2e server never came up; is the SPA build failing?")


def main() -> None:
    # Make the test package importable so we reuse the one fixture-DB builder.
    sys.path.insert(0, str(PROJECT_ROOT))
    import uvicorn
    from tests.conftest import LEAGUE_ID, _build_database

    mixed = "--mixed" in sys.argv[1:]
    port = MIXED_PORT if mixed else PORT
    e2e_dir = PROJECT_ROOT / "web" / ".e2e"
    e2e_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = e2e_dir / ("legacy-for-mixed.db" if mixed else "fixture.db")
    db_path = e2e_dir / ("mixed.db" if mixed else "fixture.db")
    for path in {legacy_path, db_path}:
        for stale in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            stale.unlink(missing_ok=True)
    _build_database(legacy_path)
    if mixed:
        from tests.sleeper_fixture import build_mixed_era_db

        build_mixed_era_db(legacy_path, db_path, LEAGUE_ID)

    if mixed:
        _wait_for_build()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["DASHBOARD_STATIC_DIR"] = str(PROJECT_ROOT / "web" / "dist")
    os.environ["DASHBOARD_PORT"] = str(port)

    # The compact e2e fixture intentionally has four teams per season, while
    # the reviewed production artifact has twelve. Supply a deterministic
    # fixture-only source so browser tests exercise the real grouping, weekly
    # record, API, and presentation path without weakening production mapping.
    from ff_pipeline.repository.models import Team
    from sqlalchemy import select

    from ff_dashboard.analytics import conferences
    from ff_dashboard.analytics.historical_divisions import (
        HistoricalDivision,
        HistoricalDivisionSeason,
        HistoricalDivisionTeam,
    )
    from ff_dashboard.api.main import create_app

    def fixture_source(session, season_id: int, year: int):  # type: ignore[no-untyped-def]
        if year >= 2020:
            return None, {}, []
        team_ids = list(
            session.execute(
                select(Team.team_id).where(Team.season_id == season_id).order_by(Team.team_id)
            ).scalars()
        )
        mapping = {index: int(team_id) for index, team_id in enumerate(team_ids, start=1)}
        source = HistoricalDivisionSeason(
            season=year,
            source_url="fixture://historical-divisions",
            captured_at="2026-06-17",
            divisions=(
                HistoricalDivision(
                    division_number=1,
                    name="Westeros",
                    teams=tuple(
                        HistoricalDivisionTeam(index, rank, index)
                        for rank, index in enumerate((1, 2), start=1)
                    ),
                ),
                HistoricalDivision(
                    division_number=2,
                    name="Essos",
                    teams=tuple(
                        HistoricalDivisionTeam(index, rank, index)
                        for rank, index in enumerate((3, 4), start=1)
                    ),
                ),
            ),
        )
        return source, mapping, []

    conferences._mapped_source = fixture_source
    app = create_app()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
