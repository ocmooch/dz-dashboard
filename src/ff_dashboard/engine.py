"""Read-only SQLAlchemy engine over the Phase 1 database.

The dashboard is a *reader*; Phase 1's pipeline is the only writer and takes a
file lock while it runs. We open SQLite connections with:

* ``PRAGMA query_only = ON`` — the connection rejects any write, so a stray
  ``INSERT/UPDATE/DELETE`` fails loudly instead of corrupting the writer's data.
  This is the enforcement behind the "BFF never writes" boundary.
* ``PRAGMA busy_timeout`` — a read waits briefly for the writer's lock instead
  of erroring out, so a dashboard request during a pipeline run does not 500.
* WAL journal mode (best-effort) — lets readers and the single writer proceed
  concurrently. WAL is a persistent property the writer sets; a read-only
  connection cannot change it, so we only request it when the file allows.

The engine is stored on ``app.state`` so tests can bind a temp-file engine
without monkey-patching (the same pattern Phase 1 uses).
"""

from __future__ import annotations

import contextlib
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.event import listens_for

BUSY_TIMEOUT_MS = 5000


def create_readonly_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create an engine whose connections are read-only and lock-tolerant."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        # Allow the engine to be shared across FastAPI's threadpool workers.
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, echo=echo, future=True, connect_args=connect_args)

    if engine.dialect.name == "sqlite":
        _install_readonly_pragmas(engine)

    return engine


def _install_readonly_pragmas(engine: Engine) -> None:
    @listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        # Best-effort WAL; readers cannot switch an existing rollback-journal DB,
        # and that is fine — the writer owns journal mode.
        with contextlib.suppress(Exception):
            cursor.execute("PRAGMA journal_mode = WAL")
        # Hard read-only guard. Set last so the WAL attempt above is permitted.
        cursor.execute("PRAGMA query_only = ON")
        cursor.close()
