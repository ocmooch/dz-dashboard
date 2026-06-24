"""Owner / manager career metrics.

Career numbers key on ``owner_id`` and aggregate the per-season regular-season
records (so they agree with the standings to the decimal), plus championships
and finishes from ``seasons`` / ``teams``.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Owner, Season, Team
from ff_pipeline.repository.queries import get_owner
from sqlalchemy import func, select

from ff_dashboard.analytics.bracket import (
    TIER_CONSOLATION,
    postseason_classification,
    season_sacko_map,
)
from ff_dashboard.analytics.common import (
    SIGNIFICANT_STINT_SEASONS,
    owner_name_map,
    owner_qualified_map,
    played_season_ids,
)
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _season_result(final_rank: int | None, is_champion: bool, is_sacko: bool = False) -> str | None:
    """A human label for a completed season's finish, or None when no rank yet.

    Returned for every completed season (incl. 2010-2015): champion / Sacko /
    runner-up / 3rd / Nth. ``None`` (a gap, never 0) when ``final_rank`` is absent —
    an in-progress or rank-less season. The ``Sacko`` (toilet-bowl loser) brand
    takes precedence over the bare ``Nth`` finish.
    """
    if is_champion:
        return "Champion"
    if is_sacko:
        return "Sacko"
    if final_rank is None:
        return None
    if final_rank == 1:
        return "1st place"
    if final_rank == 2:
        return "Runner-up"
    if final_rank == 3:
        return "3rd place"
    return f"{final_rank}th"


def _playoff_participation(session: Session) -> tuple[dict[int, set[int]], set[int]]:
    """``(made_by_season, derivable_season_ids)``.

    ``made_by_season[season_id]`` is the set of teams with ≥1 ``is_playoff``
    matchup that is **not** a consolation/toilet-bowl game — classified by the
    shared bracket connectivity split (``postseason_classification``), not the
    unpopulated ``is_consolation`` source column.

    ``derivable_season_ids`` are the seasons where ``made_playoffs`` can be stated
    honestly — i.e. the playoff flag selects a **proper subset** of the league
    (``0 < made < teams_that_season``). When *every* post-season team is
    indistinguishable (the bracket can't be split, so all are tier ``playoff``) the
    set spans the whole field → ``made_playoffs`` is **unknown** (``None``), never a
    fabricated True/False.
    """
    made_by_season: dict[int, set[int]] = {}
    class_cache: dict[int, dict[str, Any]] = {}
    for team_id, season_id, matchup_id, is_playoff in session.execute(
        select(Matchup.team_id, Matchup.season_id, Matchup.matchup_id, Matchup.is_playoff)
    ).all():
        if not is_playoff:
            continue
        sid = int(season_id)
        cls = class_cache.get(sid)
        if cls is None:
            cls = postseason_classification(session, sid)
            class_cache[sid] = cls
        entry = cls["by_matchup_id"].get(int(matchup_id))
        if entry is not None and entry["tier"] == TIER_CONSOLATION:
            continue
        made_by_season.setdefault(sid, set()).add(int(team_id))
    teams_per_season = {
        int(sid): int(n)
        for sid, n in session.execute(
            select(Team.season_id, func.count()).group_by(Team.season_id)
        ).all()
    }
    derivable = {
        sid for sid, made in made_by_season.items() if 0 < len(made) < teams_per_season.get(sid, 0)
    }
    return made_by_season, derivable


def _standings_index(session: Session) -> dict[int, dict[str, Any]]:
    """team_id -> its regular-season standings row, across every played season."""
    index: dict[int, dict[str, Any]] = {}
    played = played_season_ids(session)
    seasons = session.execute(select(Season)).scalars().all()
    for season in seasons:
        if int(season.season_id) not in played:
            continue
        snap = compute_standings(session, season.season_id)
        if snap is None:  # pragma: no cover
            continue
        for row in snap["rows"]:
            index[row["team_id"]] = {**row, "season_year": season.year}
    return index


def owner_seasons(session: Session, owner_id: int) -> list[dict[str, Any]] | None:
    """Season-by-season table for one owner (None if the owner doesn't exist)."""
    if get_owner(session, owner_id) is None:
        return None
    index = _standings_index(session)
    champions = {s.champion_team_id for s in session.execute(select(Season)).scalars().all()}
    played = played_season_ids(session)
    teams = [
        t
        for t in session.execute(select(Team).where(Team.owner_id == owner_id)).scalars().all()
        if int(t.season_id) in played
    ]
    season_year: dict[int, int] = {
        int(sid): int(yr)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
    }
    made_by_season, derivable_seasons = _playoff_participation(session)
    sacko_map = season_sacko_map(session)

    rows: list[dict[str, Any]] = []
    for team in teams:
        srow = index.get(team.team_id, {})
        is_champion = team.team_id in champions
        is_sacko = sacko_map.get(int(team.season_id), {}).get("team_id") == team.team_id
        # Derive made_playoffs from the schedule (the Team column is unpopulated):
        # True/False only when the season's bracket is distinguishable, else None
        # (a gap — never fabricate; see _playoff_participation).
        if team.season_id in derivable_seasons:
            made_playoffs: bool | None = team.team_id in made_by_season[team.season_id]
        else:
            made_playoffs = None
        rows.append(
            {
                "season_id": team.season_id,
                "season_year": season_year.get(team.season_id),
                "team_id": team.team_id,
                "team_name": period_team_name(team, season_year.get(team.season_id)),
                "wins": srow.get("wins", 0),
                "losses": srow.get("losses", 0),
                "ties": srow.get("ties", 0),
                "points_for": srow.get("points_for", 0.0),
                "final_rank": team.final_rank,
                "made_playoffs": made_playoffs,
                "result": _season_result(team.final_rank, is_champion, is_sacko),
                "is_champion": is_champion,
                "is_sacko": is_sacko,
            }
        )
    rows.sort(key=lambda r: r["season_year"] or 0)
    return rows


def teams_index(session: Session) -> list[dict[str, Any]]:
    """Every team (one owner's season entry) across all played seasons, flat.

    Powers the Teams browser. Carries the same per-season record / finish the
    owner pages show, plus owner identity, so the SPA can group by season or by
    owner without doing any math itself. One pass over ``teams`` reusing the
    shared standings / playoff / finish helpers, so the numbers agree with the
    standings and owner pages to the decimal.
    """
    index = _standings_index(session)
    champions = {s.champion_team_id for s in session.execute(select(Season)).scalars().all()}
    played = played_season_ids(session)
    season_year: dict[int, int] = {
        int(sid): int(yr)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
    }
    made_by_season, derivable_seasons = _playoff_participation(session)
    sacko_map = season_sacko_map(session)
    owners = owner_name_map(session)

    rows: list[dict[str, Any]] = []
    for team in session.execute(select(Team)).scalars().all():
        if int(team.season_id) not in played:
            continue
        srow = index.get(team.team_id, {})
        is_champion = team.team_id in champions
        is_sacko = sacko_map.get(int(team.season_id), {}).get("team_id") == team.team_id
        if team.season_id in derivable_seasons:
            made_playoffs: bool | None = team.team_id in made_by_season[team.season_id]
        else:
            made_playoffs = None
        rows.append(
            {
                "owner_id": team.owner_id,
                "owner_name": owners.get(team.owner_id),
                "season_id": team.season_id,
                "season_year": season_year.get(team.season_id),
                "team_id": team.team_id,
                "team_name": period_team_name(team, season_year.get(team.season_id)),
                "wins": srow.get("wins", 0),
                "losses": srow.get("losses", 0),
                "ties": srow.get("ties", 0),
                "points_for": srow.get("points_for", 0.0),
                "final_rank": team.final_rank,
                "made_playoffs": made_playoffs,
                "result": _season_result(team.final_rank, is_champion, is_sacko),
                "is_champion": is_champion,
                "is_sacko": is_sacko,
            }
        )
    # Newest season first, then by finish within a season; team_id breaks ties so
    # the order is stable for an unranked / in-progress season.
    rows.sort(key=lambda r: (-(r["season_year"] or 0), r["final_rank"] or 99, r["team_id"]))
    return rows


def _career_from_seasons(
    owner_id: int, display_name: str | None, rows: list[dict[str, Any]], *, is_active: bool
) -> dict[str, Any]:
    finishes = [r["final_rank"] for r in rows if r["final_rank"] is not None]
    championships = [r for r in rows if r["is_champion"]]
    sackos = [r for r in rows if r.get("is_sacko")]
    latest = max(rows, key=lambda r: r.get("season_year") or 0, default=None)
    seasons_played = len(rows)
    return {
        "owner_id": owner_id,
        "display_name": display_name,
        "seasons_played": seasons_played,
        "total_wins": sum(r["wins"] for r in rows),
        "total_losses": sum(r["losses"] for r in rows),
        "total_ties": sum(r["ties"] for r in rows),
        "total_points_for": round(sum(r["points_for"] for r in rows), 2),
        "championships": len(championships),
        "sackos": len(sackos),
        "best_finish": min(finishes) if finishes else None,
        "avg_finish": round(mean(finishes), 2) if finishes else None,
        "latest_team_id": latest["team_id"] if latest else None,
        # Activity + tenure travel with the career row so the managers table can
        # rank the rate-based "best of" stats without recomputing eligibility:
        # an active manager always qualifies; a departed one only once they have a
        # significant stint. See ``common.SIGNIFICANT_STINT_SEASONS``.
        "is_active": is_active,
        "qualified": is_active or seasons_played >= SIGNIFICANT_STINT_SEASONS,
    }


def owner_career(session: Session, owner_id: int) -> dict[str, Any] | None:
    """Career aggregate + trophy case for one owner (None if not found)."""
    owner = get_owner(session, owner_id)
    if owner is None:
        return None
    rows = owner_seasons(session, owner_id) or []
    career = _career_from_seasons(
        owner_id, owner.display_name, rows, is_active=bool(owner.is_active)
    )
    # Hardware strip: podium finishes (the trophies) plus every Sacko season (the
    # 💩 anti-trophy), so the disgrace is recorded alongside the glory.
    trophy_case = [
        {
            "season_year": r["season_year"],
            "team_name": r["team_name"],
            "finish": r["final_rank"],
            "is_champion": r["is_champion"],
            "is_sacko": r.get("is_sacko", False),
        }
        for r in rows
        if r["is_champion"]
        or r.get("is_sacko")
        or (r["final_rank"] is not None and r["final_rank"] <= 3)
    ]
    return {
        **career,
        "trophy_case": trophy_case,
        "consistency": owner_consistency(session, owner_id),
    }


def owner_consistency(session: Session, owner_id: int) -> dict[str, Any] | None:
    """Weekly scoring consistency for one owner, ranked against current peers."""
    if get_owner(session, owner_id) is None:
        return None

    owners = list(session.execute(select(Owner)).scalars().all())
    per_owner: dict[int, list[float]] = {int(o.owner_id): [] for o in owners}
    team_to_owner = {
        int(tid): int(oid)
        for tid, oid in session.execute(select(Team.team_id, Team.owner_id)).all()
    }
    rows = session.execute(
        select(Matchup.team_id, Matchup.team_score, Matchup.opponent_team_id).where(
            Matchup.team_score.is_not(None), Matchup.opponent_team_id.is_not(None)
        )
    ).all()
    for team_id, score, _ in rows:
        oid = team_to_owner.get(int(team_id))
        if oid is not None:
            per_owner.setdefault(oid, []).append(float(score))

    # Rank only against owners who qualify (active or a significant stint), so a
    # short-stint departed owner's few weeks don't dilute the denominator or skew
    # the steady/boom-bust midpoint. The subject is always kept in the pool so
    # their own profile still shows a rank, even when they don't otherwise qualify.
    qualified = owner_qualified_map(session)
    ranked: list[tuple[int, float]] = [
        (oid, pstdev(scores))
        for oid, scores in per_owner.items()
        if len(scores) >= 2 and (qualified.get(oid, True) or oid == owner_id)
    ]
    ranked.sort(key=lambda item: item[1])
    rank_by_owner = {oid: i for i, (oid, _) in enumerate(ranked, start=1)}
    scores = per_owner.get(owner_id, [])

    season_rows = owner_seasons(session, owner_id) or []
    scored_seasons = [r for r in season_rows if r["points_for"] and r["points_for"] > 0]
    best = max(scored_seasons, key=lambda r: r["points_for"]) if scored_seasons else None

    if len(scores) < 2:
        return {
            "available": False,
            "reason": "no_scored_data",
            "weekly_points_stdev": None,
            "rank_among_owners": None,
            "best_season_year": best["season_year"] if best else None,
            "best_season_points_for": best["points_for"] if best else None,
            "signature": None,
        }

    stdev = round(pstdev(scores), 2)
    rank = rank_by_owner.get(owner_id)
    midpoint = (len(ranked) + 1) / 2 if ranked else 0
    signature = "steady scorer" if rank is not None and rank <= midpoint else "boom/bust"
    return {
        "available": True,
        "reason": None,
        "weekly_points_stdev": stdev,
        "rank_among_owners": rank,
        "best_season_year": best["season_year"] if best else None,
        "best_season_points_for": best["points_for"] if best else None,
        "signature": signature,
    }


def list_owners_career(session: Session) -> list[dict[str, Any]]:
    """Career line for every owner, ranked by championships then wins."""
    owners = list(session.execute(select(Owner)).scalars().all())
    by_owner: dict[int, list[dict[str, Any]]] = {}
    for o in owners:
        by_owner[o.owner_id] = owner_seasons(session, o.owner_id) or []
    careers = [
        _career_from_seasons(
            o.owner_id, o.display_name, by_owner[o.owner_id], is_active=bool(o.is_active)
        )
        for o in owners
    ]
    careers.sort(key=lambda c: (-c["championships"], -c["total_wins"], -c["total_points_for"]))
    return careers


def owner_trajectory(session: Session, owner_id: int) -> list[dict[str, Any]] | None:
    """Final rank + points-for per season, for the trajectory chart."""
    rows = owner_seasons(session, owner_id)
    if rows is None:
        return None
    return [
        {
            "season_year": r["season_year"],
            "final_rank": r["final_rank"],
            "points_for": r["points_for"],
        }
        for r in rows
    ]
