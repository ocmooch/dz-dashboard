"""Owners / managers endpoints (career, seasons, trajectory, rivalries)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from ff_pipeline.api._meta import build_meta
from ff_pipeline.api.errors import not_found
from ff_pipeline.repository.queries import get_owner

from ff_dashboard.analytics.commissioners import commissioner_history
from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.head_to_head import pairwise_record, rivalry_matrix
from ff_dashboard.analytics.owners import (
    list_owners_career,
    owner_career,
    owner_seasons,
    owner_trajectory,
)
from ff_dashboard.api.deps import SessionDep  # noqa: TC001 — runtime dep for FastAPI
from ff_dashboard.api.schemas import (
    CommissionerTerm,
    Envelope,
    HeadToHead,
    OwnerCareer,
    OwnerSeasons,
    OwnersList,
    OwnerTrajectory,
    RivalryMatrix,
)

router = APIRouter(tags=["owners"])


@router.get("/v1/owners", response_model=Envelope[OwnersList])
def list_owners(session: SessionDep) -> Envelope[OwnersList]:
    require_league(session)
    careers = [OwnerCareer(**c) for c in list_owners_career(session)]
    return Envelope(data=OwnersList(owners=careers), meta=build_meta(session))


# Declared before /v1/owners/{owner_id} — but {owner_id} is an int path param,
# so "rivalry-matrix" never matches it; the explicit order is just clarity.
@router.get("/v1/owners/rivalry-matrix", response_model=Envelope[RivalryMatrix])
def get_rivalry_matrix(session: SessionDep) -> Envelope[RivalryMatrix]:
    require_league(session)
    return Envelope(data=RivalryMatrix(**rivalry_matrix(session)), meta=build_meta(session))


@router.get("/v1/owners/{owner_id}", response_model=Envelope[OwnerCareer])
def get_owner_career(owner_id: int, session: SessionDep) -> Envelope[OwnerCareer]:
    data = owner_career(session, owner_id)
    if data is None:
        raise not_found(f"No owner with id {owner_id}")
    all_terms = commissioner_history(session)
    owner_terms = [CommissionerTerm(**asdict(t)) for t in all_terms if t.owner_id == owner_id]
    return Envelope(
        data=OwnerCareer(**data, commissioner_terms=owner_terms),
        meta=build_meta(session),
    )


@router.get("/v1/owners/{owner_id}/seasons", response_model=Envelope[OwnerSeasons])
def get_owner_seasons(owner_id: int, session: SessionDep) -> Envelope[OwnerSeasons]:
    rows = owner_seasons(session, owner_id)
    if rows is None:
        raise not_found(f"No owner with id {owner_id}")
    owner = get_owner(session, owner_id)
    return Envelope(
        data=OwnerSeasons(
            owner_id=owner_id,
            display_name=owner.display_name if owner else None,
            seasons=rows,
        ),
        meta=build_meta(session),
    )


@router.get("/v1/owners/{owner_id}/trajectory", response_model=Envelope[OwnerTrajectory])
def get_owner_trajectory(owner_id: int, session: SessionDep) -> Envelope[OwnerTrajectory]:
    points = owner_trajectory(session, owner_id)
    if points is None:
        raise not_found(f"No owner with id {owner_id}")
    owner = get_owner(session, owner_id)
    return Envelope(
        data=OwnerTrajectory(
            owner_id=owner_id,
            display_name=owner.display_name if owner else None,
            points=points,
        ),
        meta=build_meta(session),
    )


@router.get(
    "/v1/owners/{owner_id}/head-to-head/{other_owner_id}",
    response_model=Envelope[HeadToHead],
)
def get_head_to_head(
    owner_id: int, other_owner_id: int, session: SessionDep
) -> Envelope[HeadToHead]:
    if get_owner(session, owner_id) is None:
        raise not_found(f"No owner with id {owner_id}")
    if get_owner(session, other_owner_id) is None:
        raise not_found(f"No owner with id {other_owner_id}")
    data = pairwise_record(session, owner_id, other_owner_id)
    return Envelope(data=HeadToHead(**data), meta=build_meta(session))
