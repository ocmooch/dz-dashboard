"""Dashboard settings, loaded from environment + ``.env``.

Unlike Phase 1, the dashboard needs no secrets (no cookie, no league id) —
it only reads the database Phase 1 produced. The one setting that matters is
``DATABASE_URL``: it must point at the *live* Phase 1 SQLite file so the
dashboard always reflects the latest pipeline run, read-only.

Paths/URLs are resolved so a relative SQLite path means the same file
regardless of the working directory the server is launched from. The default
points at the sibling ``danger-zone`` checkout (``../danger-zone/data/fantasy.db``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Default to the sibling Phase 1 checkout's live database.
_DEFAULT_DB = (PROJECT_ROOT.parent / "danger-zone" / "data" / "fantasy.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{_DEFAULT_DB}"


class Settings(BaseSettings):
    """All dashboard configuration. One source of truth."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database (the only data source; read-only) ---
    database_url: str = DEFAULT_DATABASE_URL

    # --- Asset store (team logos; read-only, on disk) ---
    # Phase 1 stores avatar *bytes* on disk under a content-addressed path; the
    # DB row only holds the relative ``storage_path``. This points at that root
    # so the BFF can stream a team logo. Unset → derived next to the DB file
    # (``<db_dir>/assets``), matching Phase 1's layout. Never written.
    assets_root: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("DASHBOARD_ASSETS_ROOT", "ASSETS_ROOT"),
    )

    # --- API server ---
    host: str = Field("127.0.0.1", validation_alias=AliasChoices("DASHBOARD_HOST", "HOST"))
    port: int = Field(8800, validation_alias=AliasChoices("DASHBOARD_PORT", "PORT"))

    # --- CORS (the Vite dev server origin) ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"],
        validation_alias=AliasChoices("DASHBOARD_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- Static SPA (production-ish single-origin local run) ---
    # When set to a built ``web/dist`` directory, the BFF also serves the SPA so
    # one uvicorn process is the whole dashboard (no separate Vite/static server,
    # no CORS). Unset in dev, where Vite serves the SPA and proxies the API.
    static_dir: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("DASHBOARD_STATIC_DIR", "STATIC_DIR"),
    )

    def resolved_static_dir(self) -> Path | None:
        """Return ``static_dir`` as an absolute path (relative paths resolve
        against the project root), or ``None`` if unset."""
        if self.static_dir is None:
            return None
        path = self.static_dir
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    def resolved_assets_root(self) -> Path:
        """Return the on-disk avatar asset-store root as an absolute path.

        When ``assets_root`` is unset, derive it next to the resolved SQLite DB
        file (``<db_dir>/assets``) — Phase 1's default layout. A relative
        configured path resolves against the project root. The path is not
        required to exist; the avatar route 404s gracefully when a file is
        missing so the UI falls back to a monogram.
        """
        if self.assets_root is not None:
            path = self.assets_root
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return path.resolve()
        url = self.resolved_database_url()
        prefix = "sqlite:///"
        if url.startswith(prefix):
            db_path = Path(url[len(prefix) :])
            return (db_path.parent / "assets").resolve()
        # Non-SQLite (e.g. Postgres path) — fall back to the sibling default.
        return (_DEFAULT_DB.parent / "assets").resolve()

    def resolved_database_url(self) -> str:
        """Return ``database_url`` with any relative SQLite path made absolute
        against the project root, so the CWD never changes which file we read."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url
        raw = self.database_url[len(prefix) :]
        if not raw or raw == ":memory:" or raw.startswith("/"):
            return self.database_url
        absolute = (PROJECT_ROOT / raw).resolve()
        return f"{prefix}{absolute}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor used by the server and CLI."""
    return Settings()
