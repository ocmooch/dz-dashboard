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


def main() -> None:
    # Make the test package importable so we reuse the one fixture-DB builder.
    sys.path.insert(0, str(PROJECT_ROOT))
    import uvicorn
    from tests.conftest import _build_database

    e2e_dir = PROJECT_ROOT / "web" / ".e2e"
    e2e_dir.mkdir(parents=True, exist_ok=True)
    db_path = e2e_dir / "fixture.db"
    for stale in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        stale.unlink(missing_ok=True)
    _build_database(db_path)

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["DASHBOARD_STATIC_DIR"] = str(PROJECT_ROOT / "web" / "dist")
    os.environ["DASHBOARD_PORT"] = str(PORT)

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
        port=PORT,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
