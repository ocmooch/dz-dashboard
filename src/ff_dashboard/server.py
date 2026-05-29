"""``dz-dashboard`` CLI entrypoint.

``dz-dashboard serve`` launches the analytics API with uvicorn against the
configured (read-only) database. Kept intentionally tiny — the dashboard has no
write commands, no pipeline control; it only serves reads.
"""

from __future__ import annotations

import typer
import uvicorn

from ff_dashboard.settings import get_settings

app = typer.Typer(add_completion=False, help="Danger Zone analytics dashboard (Phase 2 BFF).")


@app.command()
def serve(
    host: str | None = typer.Option(None, help="Bind host (default from settings)."),
    port: int | None = typer.Option(None, help="Bind port (default from settings)."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev)."),
) -> None:
    """Run the analytics API server."""
    settings = get_settings()
    uvicorn.run(
        "ff_dashboard.api.main:create_app",
        factory=True,
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


@app.command()
def info() -> None:
    """Print the resolved configuration (no secrets — there are none)."""
    settings = get_settings()
    typer.echo(f"database_url : {settings.resolved_database_url()}")
    typer.echo(f"bind         : {settings.host}:{settings.port}")
    typer.echo(f"cors_origins : {settings.cors_origins}")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
