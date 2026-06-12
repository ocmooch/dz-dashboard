"""Conference (division) standings for the league era 2010-2019.

Phase 1 stores ``season_conferences`` rows and ``teams.conference_id`` FK.
This module provides helpers consumed by standings, bracket, and the
dedicated conferences endpoint. Seasons without conference assignments
(2020+) return ``available=False``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from ff_pipeline.repository.models import SeasonConference, Team  # type: ignore[attr-defined]
    from ff_pipeline.repository.queries import get_season, list_conferences_for_season  # type: ignore[attr-defined]
    from sqlalchemy import select
    _CONFERENCE_MODELS_AVAILABLE = True
except (ImportError, AttributeError):
    _CONFERENCE_MODELS_AVAILABLE = False

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def conference_map(session: Session, season_id: int) -> dict[int, tuple[int | None, str | None]]:
    """Return ``{team_id: (conference_id, conference_name)}`` for every team in the season.

    Both values are ``None`` for post-2019 seasons (no conference assignments).
    Returns empty dict when conference models are not yet available in ff_pipeline.
    """
    if not _CONFERENCE_MODELS_AVAILABLE:
        return {}
    rows = session.execute(
        select(Team.team_id, Team.conference_id, SeasonConference.name)
        .join(
            SeasonConference,
            Team.conference_id == SeasonConference.conference_id,
            isouter=True,
        )
        .where(Team.season_id == season_id)
    ).all()
    return {
        int(team_id): (
            int(conference_id) if conference_id is not None else None,
            conf_name,
        )
        for team_id, conference_id, conf_name in rows
    }


def season_conferences(session: Session, season_id: int) -> dict[str, Any] | None:
    """Return conference-grouped standings for *season_id*.

    Returns ``None`` when the season is not found. Returns ``available=False``
    for seasons without conference assignments (2020 and later) or when
    conference models are not yet available in ff_pipeline.
    """
    if not _CONFERENCE_MODELS_AVAILABLE:
        return {"season_id": season_id, "season_year": None, "available": False, "reason": "no_conferences_this_season", "conferences": []}
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None

    confs = list_conferences_for_season(session, season_id)
    base: dict[str, Any] = {"season_id": season_id, "season_year": season.year}

    if not confs:
        return {
            **base,
            "available": False,
            "reason": "no_conferences_this_season",
            "conferences": [],
        }

    overall = compute_standings(session, season_id) or {}
    team_stats: dict[int, dict[str, Any]] = {r["team_id"]: r for r in overall.get("rows", [])}

    # Group team_id → conference_id for this season
    tid_rows = session.execute(
        select(Team.team_id, Team.conference_id).where(Team.season_id == season_id)
    ).all()
    conf_teams: dict[int, list[dict[str, Any]]] = {c.conference_id: [] for c in confs}
    for team_id_raw, conf_id_raw in tid_rows:
        team_id = int(team_id_raw)
        conf_id = int(conf_id_raw) if conf_id_raw is not None else None
        if conf_id is not None and conf_id in conf_teams:
            ts = team_stats.get(team_id)
            if ts:
                entry = dict(ts)
                entry["conference_rank"] = 0  # filled below
                conf_teams[conf_id].append(entry)

    conferences_out: list[dict[str, Any]] = []
    for conf in sorted(confs, key=lambda c: c.division_number):
        members = conf_teams.get(conf.conference_id, [])
        members = sorted(members, key=lambda r: (-r["wins"], -r["points_for"]))
        for i, t in enumerate(members, 1):
            t["conference_rank"] = i
        conferences_out.append(
            {
                "conference_id": conf.conference_id,
                "division_number": conf.division_number,
                "name": conf.name,
                "teams": members,
            }
        )

    return {**base, "available": True, "reason": None, "conferences": conferences_out}
