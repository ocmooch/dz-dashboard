"""Season provenance and capabilities (Sleeper D1).

Thin, read-only wrappers over upstream ``ff_pipeline.repository.queries`` (S8):
``season_platform``, ``season_capabilities`` and ``season_freshness``. The dashboard adds only
presentation rules:

* ``not_used`` resolves **silently**: its note is dropped, and the UI renders nothing
  (``docs/sleeper/00_UPSTREAM_STATE.md`` §3, user rule).
* Platform eras span **every** season that has a platform, played or not, so the move to Sleeper
  shows before 2026 has games (user decision, D1 plan decision 3).
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries
from ff_pipeline.repository.models import Season
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

NOT_USED = "not_used"
DEFAULT_PLATFORM = "nfl_com"


def season_provenance(session: Session, season_id: int) -> dict[str, str]:
    info = queries.season_platform(session, season_id)
    if info is None:
        return {"platform": DEFAULT_PLATFORM, "platform_label": "NFL.com"}
    return {"platform": info.platform, "platform_label": info.label}


def season_capabilities(session: Session, season_id: int) -> dict[str, dict[str, str | None]]:
    """``{key: {state, note}}`` in upstream's key order; ``not_used`` carries no note."""
    return {
        key: {"state": cap.state, "note": None if cap.state == NOT_USED else cap.note}
        for key, cap in queries.season_capabilities(session, season_id).items()
    }


def season_platform_fields(session: Session, season_id: int) -> dict[str, Any]:
    """The additive block every season-level payload carries (D1 plan decision 1)."""
    return {
        **season_provenance(session, season_id),
        "capabilities": season_capabilities(session, season_id),
    }


def _league_seasons(session: Session) -> list[Season]:
    return list(session.scalars(select(Season).order_by(Season.year)))


def platform_eras(session: Session) -> list[dict[str, Any]]:
    """Contiguous runs of seasons on one platform: ``[{platform, label, start_year, end_year}]``.

    ``end_year`` is ``None`` for the run that includes the newest season (still current)."""
    eras: list[dict[str, Any]] = []
    for s in _league_seasons(session):
        prov = season_provenance(session, s.season_id)
        if eras and eras[-1]["platform"] == prov["platform"]:
            eras[-1]["end_year"] = s.year
            continue
        eras.append(
            {
                "platform": prov["platform"],
                "label": prov["platform_label"],
                "start_year": s.year,
                "end_year": s.year,
            }
        )
    if eras:
        eras[-1]["end_year"] = None
    return eras


def platform_changes(session: Session) -> list[dict[str, Any]]:
    """The first season of each platform after the first: ``[{season_year, from, to}]``."""
    eras = platform_eras(session)
    return [
        {
            "season_year": cur["start_year"],
            "from_label": prev["label"],
            "to_label": cur["label"],
            "to_platform": cur["platform"],
        }
        for prev, cur in pairwise(eras)
    ]


def current_season(session: Session) -> dict[str, int | None]:
    """The in-progress season and its current week (the newest provisional or finalized week)."""
    for s in reversed(_league_seasons(session)):
        if s.status != "in_progress":
            continue
        fresh = queries.season_freshness(session, s.season_id)
        week: int | None = None
        if fresh is not None:
            weeks = [*fresh.provisional_weeks]
            if fresh.last_finalized_week is not None:
                weeks.append(fresh.last_finalized_week)
            week = max(weeks) if weeks else None
        return {"current_season_id": s.season_id, "current_week": week}
    return {"current_season_id": None, "current_week": None}


def capability_matrix(session: Session) -> dict[str, Any]:
    """Seasons by capabilities for About: ``{keys, seasons: [{season_year, platform, cells}]}``."""
    rows: list[dict[str, Any]] = []
    keys: list[str] = []
    for s in _league_seasons(session):
        caps = season_capabilities(session, s.season_id)
        if not keys:
            keys = list(caps)
        prov = season_provenance(session, s.season_id)
        rows.append(
            {
                "season_id": s.season_id,
                "season_year": s.year,
                "platform": prov["platform"],
                "platform_label": prov["platform_label"],
                "cells": caps,
            }
        )
    return {"keys": keys, "seasons": rows}
