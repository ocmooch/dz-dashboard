"""Team-page endpoints.

A team is one owner's season entry; these five views power the team page
(overview header, roster-by-week, schedule, scoring trend, transactions). Each
404s on an unknown ``team_id`` and 503s (via ``require_league``) when the
pipeline has never run.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found
from ff_pipeline.repository.models import Asset, Team

from ff_dashboard.analytics.teams import (
    team_overview,
    team_roster,
    team_schedule,
    team_scoring_trend,
    team_transactions,
)
from ff_dashboard.analytics.transactions import derive_roster_moves
from ff_dashboard.api.deps import (  # noqa: TC001 — runtime deps for FastAPI
    AssetsRootDep,
    CacheDep,
    SessionDep,
)
from ff_dashboard.api.schemas import (
    Envelope,
    TeamOverview,
    TeamRosterMoves,
    TeamRosterOut,
    TeamSchedule,
    TeamScoringTrend,
    TeamTransactions,
)

router = APIRouter(tags=["teams"])


@router.get("/v1/teams/{team_id}/avatar", include_in_schema=False)
def get_team_avatar(team_id: int, session: SessionDep, assets_root: AssetsRootDep) -> FileResponse:
    """Stream a team's season logo from the on-disk asset store.

    404s — never errors — when the team is unknown, has no avatar, the store is
    unconfigured, or the bytes are missing on disk, so the SPA falls back to its
    monogram chip (Q11: real logos where Phase 1 has them, monogram everywhere
    else). Owner avatars are not exposed: zero rows are populated in the source
    DB, so they remain a true source gap pending an upstream backfill. Excluded
    from the OpenAPI schema (binary, not part of the typed JSON contract).
    """
    if assets_root is None:
        raise not_found(f"No avatar for team {team_id}")
    team = session.get(Team, team_id)
    if team is None or team.team_avatar_asset_id is None:
        raise not_found(f"No avatar for team {team_id}")
    asset = session.get(Asset, team.team_avatar_asset_id)
    if asset is None:
        raise not_found(f"No avatar for team {team_id}")

    root = assets_root.resolve()
    candidate = (root / asset.storage_path).resolve()
    # Content-addressed paths are trusted, but guard against a malformed
    # ``storage_path`` escaping the asset root, and confirm the file exists.
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise not_found(f"No avatar for team {team_id}")

    return FileResponse(
        candidate,
        media_type=asset.content_type or "application/octet-stream",
        # Content-addressed bytes never change for a given path → cache hard.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/v1/teams/{team_id}", response_model=Envelope[TeamOverview])
def get_team_overview(team_id: int, session: SessionDep, cache: CacheDep) -> Envelope[TeamOverview]:
    data = cache.get_or_compute(
        session, f"team_overview:{team_id}", lambda: team_overview(session, team_id)
    )
    if data is None:
        raise not_found(f"No team with id {team_id}")
    return Envelope(data=TeamOverview(**data), meta=build_meta(session))


@router.get("/v1/teams/{team_id}/roster", response_model=Envelope[TeamRosterOut])
def get_team_roster(
    team_id: int,
    session: SessionDep,
    cache: CacheDep,
    week: int | None = Query(None, ge=1),
) -> Envelope[TeamRosterOut]:
    data = cache.get_or_compute(
        session, f"team_roster:{team_id}:{week}", lambda: team_roster(session, team_id, week)
    )
    if data is None:
        raise not_found(f"No team with id {team_id}")
    return Envelope(data=TeamRosterOut(**data), meta=build_meta(session))


@router.get("/v1/teams/{team_id}/schedule", response_model=Envelope[TeamSchedule])
def get_team_schedule(team_id: int, session: SessionDep, cache: CacheDep) -> Envelope[TeamSchedule]:
    data = cache.get_or_compute(
        session, f"team_schedule:{team_id}", lambda: team_schedule(session, team_id)
    )
    if data is None:
        raise not_found(f"No team with id {team_id}")
    return Envelope(data=TeamSchedule(**data), meta=build_meta(session))


@router.get("/v1/teams/{team_id}/scoring-trend", response_model=Envelope[TeamScoringTrend])
def get_team_scoring_trend(
    team_id: int, session: SessionDep, cache: CacheDep
) -> Envelope[TeamScoringTrend]:
    data = cache.get_or_compute(
        session, f"team_scoring_trend:{team_id}", lambda: team_scoring_trend(session, team_id)
    )
    if data is None:
        raise not_found(f"No team with id {team_id}")
    return Envelope(data=TeamScoringTrend(**data), meta=build_meta(session))


@router.get("/v1/teams/{team_id}/transactions", response_model=Envelope[TeamTransactions])
def get_team_transactions(
    team_id: int, session: SessionDep, cache: CacheDep
) -> Envelope[TeamTransactions]:
    data = cache.get_or_compute(
        session, f"team_transactions:{team_id}", lambda: team_transactions(session, team_id)
    )
    if data is None:
        raise not_found(f"No team with id {team_id}")
    return Envelope(data=TeamTransactions(**data), meta=build_meta(session))


@router.get("/v1/teams/{team_id}/roster-moves", response_model=Envelope[TeamRosterMoves])
def get_team_roster_moves(
    team_id: int, session: SessionDep, cache: CacheDep
) -> Envelope[TeamRosterMoves]:
    data = cache.get_or_compute(
        session, f"team_roster_moves:{team_id}", lambda: derive_roster_moves(session, team_id)
    )
    if data is None:
        raise not_found(f"No team with id {team_id}")
    return Envelope(data=TeamRosterMoves(**data), meta=build_meta(session))
