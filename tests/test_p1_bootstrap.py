"""P1 — BFF bootstrap: health, meta/coverage, read-only guard, cache."""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ff_dashboard.cache import AnalyticsCache
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta_reports_real_coverage(client: TestClient) -> None:
    resp = client.get("/v1/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["pipeline_run_id"] == KNOWN["run_id"]

    cov = body["data"]["coverage"]
    assert cov["seasons_present"] == KNOWN["seasons_present"]
    assert cov["seasons_scored"] == KNOWN["seasons_scored"]
    assert cov["scored_year_min"] == 2016
    assert cov["scored_year_max"] == 2017
    assert cov["reconstruction_complete"] is True
    # Availability is still a documented gap (docs/03_DATA_ACCESS.md). DST is now
    # scored: every scored season has scored DEF rows, so it reports complete.
    assert cov["availability_current_season_only"] is True
    assert cov["dst_scoring_complete"] is True

    assert body["data"]["latest_run"]["status"] == "success"


def test_meta_coverage_matrix_endpoint(client: TestClient) -> None:
    resp = client.get("/v1/meta/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"data", "meta"}
    data = body["data"]
    assert data["relevance"]["identity_split_candidate_count"] == 1
    assert data["relevance"]["identity_split_candidates"][0]["name_full"] == "Split Sam"
    projection_cells = {
        (cell["season_year"], cell["week"]): cell for cell in data["feeds"]["projections"]
    }
    assert projection_cells[(2017, 1)]["status"] == "present"
    assert data["reason_codes"]["projections_not_captured"]


def test_meta_on_empty_db_is_honest_not_500(empty_client: TestClient) -> None:
    resp = empty_client.get("/v1/meta")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["latest_run"]["run_id"] is None
    assert data["coverage"]["seasons_present"] == []
    assert data["coverage"]["seasons_scored"] == []
    assert data["coverage"]["reconstruction_complete"] is False


def test_engine_rejects_writes(engine: Engine) -> None:
    """The read-only guard: a stray write fails loudly instead of corrupting data."""
    with Session(engine) as s, pytest.raises(OperationalError, match="readonly"):
        s.execute(text("UPDATE leagues SET name = 'tampered'"))
        s.commit()


def test_reads_during_a_writer_lock_do_not_error(fixture_db_path, engine: Engine) -> None:
    """WAL + busy_timeout: a dashboard read coexists with a held write lock."""
    from sqlalchemy import create_engine

    writer = create_engine(f"sqlite:///{fixture_db_path}", future=True)
    write_conn = writer.connect()
    write_conn.exec_driver_sql("BEGIN IMMEDIATE")  # hold the write lock
    try:
        with Session(engine) as reader:
            count = reader.execute(text("SELECT COUNT(*) FROM seasons")).scalar_one()
            assert count == 4  # 2015-2017 played + one upcoming unplayed season
    finally:
        write_conn.exec_driver_sql("ROLLBACK")
        write_conn.close()
        writer.dispose()


def test_cache_memoizes_and_invalidates_on_new_run(tmp_path) -> None:
    """Self-contained DB so we can add a run without polluting the shared fixture."""
    from datetime import datetime

    from ff_pipeline.repository.database import Base
    from ff_pipeline.repository.models import PipelineRun
    from sqlalchemy import create_engine

    from ff_dashboard.engine import create_readonly_engine

    url = f"sqlite:///{tmp_path / 'cache.db'}"
    writer = create_engine(url, future=True)
    Base.metadata.create_all(writer)
    with Session(writer) as w:
        w.add(
            PipelineRun(
                status="success",
                mode="reconstruct",
                started_at=datetime(2018, 1, 1, tzinfo=UTC),
            )
        )
        w.commit()

    reader = create_readonly_engine(url)
    cache = AnalyticsCache()
    calls = {"n": 0}

    def compute() -> str:
        calls["n"] += 1
        return f"value-{calls['n']}"

    with Session(reader) as s:
        first = cache.get_or_compute(s, "demo", compute)
        second = cache.get_or_compute(s, "demo", compute)
    assert first == second == "value-1"
    assert calls["n"] == 1  # served from cache, no recompute

    # A new pipeline run changes the cache key -> recompute.
    with Session(writer) as w:
        w.add(
            PipelineRun(
                status="success",
                mode="incremental",
                started_at=datetime(2019, 6, 1, tzinfo=UTC),
            )
        )
        w.commit()
    with Session(reader) as s:
        third = cache.get_or_compute(s, "demo", compute)
    assert third == "value-2"
    assert calls["n"] == 2

    reader.dispose()
    writer.dispose()
