"""Data-coverage summary for ``/v1/meta``.

Reads the database to report which seasons exist, which are scored, and whether
the historical reconstruction looks complete. The frontend uses this to drive
the "data as of" indicator and the honest-gap banners described in
``docs/03_DATA_ACCESS.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from typing import cast as type_cast

from ff_pipeline.repository.models import (
    Matchup,
    Player,
    PlayerAvailability,
    PlayerIdentityLink,
    PlayerInjuryReport,
    PlayerStatsScored,
    Projection,
    Season,
    TeamRoster,
    Transaction,
)
from sqlalchemy import Integer, distinct, func, select
from sqlalchemy import cast as sql_cast

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# A documented gap from the Phase 1 reliability map that we still can't detect
# per-run: availability snapshots only exist for the current season. It's a
# property of the data source, so it stays a constant and is revisited if Phase 1
# closes the gap. (DST scoring used to live here too, hardcoded False; it is now
# data-derived — see ``dst_scoring_complete`` — because the pipeline scores it.)
AVAILABILITY_CURRENT_SEASON_ONLY = True


def seasons_present(session: Session) -> list[int]:
    """Season years with results on record (≥1 played game), ascending.

    Excludes a season created for an upcoming year that has been seeded with
    teams/rosters but has played no games yet — the coverage view must not claim
    a resultless future season. Data-driven on played matchups, never on a year
    (see ``ff_dashboard.analytics.common.played_season_ids``)."""
    stmt = (
        select(distinct(Season.year))
        .join(Matchup, Matchup.season_id == Season.season_id)
        .order_by(Season.year)
    )
    rows = session.execute(stmt).scalars().all()
    return [int(y) for y in rows]


def seasons_scored(session: Session) -> list[int]:
    """Season years that have at least one scored stat row, ascending."""
    stmt = (
        select(distinct(Season.year))
        .join(PlayerStatsScored, PlayerStatsScored.season_id == Season.season_id)
        .order_by(Season.year)
    )
    rows = session.execute(stmt).scalars().all()
    return [int(y) for y in rows]


def seasons_with_dst_scored(session: Session) -> list[int]:
    """Season years that have at least one *scored* team-defense (DEF) row.

    Joined through the player so it counts only DEF-position rows; the pipeline
    writes team-defense stats as DEF "players" and the engine scores them with
    the league's defense rules.
    """
    stmt = (
        select(distinct(Season.year))
        .join(PlayerStatsScored, PlayerStatsScored.season_id == Season.season_id)
        .join(Player, Player.player_id == PlayerStatsScored.player_id)
        .where(Player.position == "DEF")
        .order_by(Season.year)
    )
    rows = session.execute(stmt).scalars().all()
    return [int(y) for y in rows]


def dst_scoring_complete(session: Session) -> bool:
    """True when every scored season also has scored team-defense rows.

    This used to be a hardcoded ``False`` while DST scoring was deferred in the
    pipeline. Now that the pipeline ingests and scores team defense, we report it
    honestly and at season granularity: complete only when *every* scored season
    carries at least one scored DEF row, so a mid-backfill DB still reads False.
    A single team/week DEF row that is genuinely missing is a per-row gap the box
    score surfaces on its own (``team_defense_not_scored``); it does not flip this
    season-level capability flag.

    Scope of the flag (F-48 reconcile): it asserts the *presence* of scored team
    defense — "DST is scored end-to-end" — and is authoritative for that. It does
    **not** certify per-stat *value accuracy*. A separate, known upstream gap
    exists: nflverse team-defense yards/sacks read low, so some DST point values
    are understated even though the rows are present and scored. That is a
    data-quality concern tracked upstream (see ``docs/03_DATA_ACCESS.md`` and the
    danger-zone players audit), not a presence gap, so it must not flip this flag
    to False. Keep this a dev-facing fact; don't surface it to end-users as a
    coverage hole.
    """
    scored = set(seasons_scored(session))
    if not scored:
        return False
    return scored <= set(seasons_with_dst_scored(session))


def reconstruction_complete(session: Session) -> bool:
    """True when every completed season has a champion and matchup history.

    The reconstruction (Phase 1 item C5) fills champions, records, lineups, and
    matchups. We treat it as complete when no ``completed`` season is missing a
    ``champion_team_id`` or has zero matchup rows.
    """
    completed = list(
        session.execute(
            select(Season.season_id, Season.champion_team_id).where(Season.status == "completed")
        ).all()
    )
    if not completed:
        return False
    weeks_by_season: dict[int, int] = {
        int(season_id): int(count)
        for season_id, count in session.execute(
            select(Matchup.season_id, func.count(Matchup.matchup_id)).group_by(Matchup.season_id)
        ).all()
    }
    for season_id, champion_team_id in completed:
        if champion_team_id is None:
            return False
        if weeks_by_season.get(season_id, 0) == 0:
            return False
    return True


def compute_coverage(session: Session) -> dict[str, object]:
    """Assemble the full coverage payload for ``/v1/meta``."""
    scored = seasons_scored(session)
    return {
        "seasons_present": seasons_present(session),
        "seasons_scored": scored,
        "scored_year_min": scored[0] if scored else None,
        "scored_year_max": scored[-1] if scored else None,
        "reconstruction_complete": reconstruction_complete(session),
        "availability_current_season_only": AVAILABILITY_CURRENT_SEASON_ONLY,
        "dst_scoring_complete": dst_scoring_complete(session),
    }


def coverage_status_for_projection_week(
    session: Session, season_year: int, week: int
) -> dict[str, object]:
    """Projection coverage for one fantasy week.

    This is the box-score consumer's narrow read: it answers whether a missing
    projection is a player-level miss or a feed-level gap. The decision is data
    driven on rows in ``projections``, never on calendar constants.
    """
    rows, with_points, with_stats = session.execute(
        select(
            func.count(Projection.projection_id),
            func.count(Projection.projected_points),
            func.sum(sql_cast(Projection.projected_stats.is_not(None), Integer)),
        ).where(Projection.season_year == season_year, Projection.week == week)
    ).one()
    row_count = int(rows or 0)
    if row_count == 0:
        return {
            "status": "absent",
            "reason": "projections_not_captured",
            "row_count": 0,
            "projected_points_count": 0,
            "projected_stats_count": 0,
        }
    points_count = int(with_points or 0)
    stats_count = int(with_stats or 0)
    status = "present" if points_count or stats_count else "partial"
    reason = None if status == "present" else "projection_points_not_scored"
    return {
        "status": status,
        "reason": reason,
        "row_count": row_count,
        "projected_points_count": points_count,
        "projected_stats_count": stats_count,
    }


def compute_coverage_matrix(session: Session) -> dict[str, object]:
    """Data-driven relevance + feed coverage matrix for ``/v1/meta/coverage``."""
    relevance = _relevance_summary(session)
    return {
        "relevance": relevance,
        "feeds": {
            "rosters": _season_week_cells(session, TeamRoster.season_year, TeamRoster.week),
            "scored_stats": _season_week_cells(
                session,
                Season.year,
                PlayerStatsScored.week,
                join_model=PlayerStatsScored,
                join_on=PlayerStatsScored.season_id == Season.season_id,
            ),
            "injuries": _season_week_cells(
                session,
                PlayerInjuryReport.season_year,
                PlayerInjuryReport.week,
                pre_league_before=min(seasons_present(session), default=None),
            ),
            "projections": _projection_cells(session),
            "transactions": _season_week_cells(
                session,
                Season.year,
                Transaction.effective_week,
                join_model=Transaction,
                join_on=Transaction.season_id == Season.season_id,
            ),
            "availability": _season_week_cells(
                session, PlayerAvailability.season_year, PlayerAvailability.week
            ),
        },
        "reason_codes": {
            "not_captured": "Source never recorded this cell.",
            "projections_not_captured": "Projection feed has no row for this season/week.",
            "projection_points_not_scored": "Projection rows exist but projected fantasy points were not scored.",
            "pre_league": "Raw source rows predate the league coverage window.",
            "unscored_season": "Season has no per-player scored-stat rows.",
            "current_season_only": "Source only records the current season.",
            "identity_split_candidate": "A rostered player has a same-name stats/injury twin.",
            "genuine_zero": "A real zero, not a missing-data gap.",
        },
    }


def _season_week_cells(
    session: Session,
    season_col: Any,
    week_col: Any,
    *,
    join_model: Any | None = None,
    join_on: Any | None = None,
    pre_league_before: int | None = None,
) -> list[dict[str, object]]:
    stmt = (
        select(season_col, week_col, func.count())
        .group_by(season_col, week_col)
        .order_by(season_col, week_col)
    )
    if join_model is not None and join_on is not None:
        stmt = stmt.select_from(Season).join(join_model, join_on)
    cells: list[dict[str, object]] = []
    for season_year, week, count in session.execute(stmt).all():
        if season_year is None or week is None:
            continue
        reason = (
            "pre_league"
            if pre_league_before is not None and int(season_year) < pre_league_before
            else None
        )
        cells.append(
            {
                "season_year": int(season_year),
                "week": int(week),
                "status": "not_applicable" if reason == "pre_league" else "present",
                "reason": reason,
                "row_count": int(count),
            }
        )
    return cells


def _projection_cells(session: Session) -> list[dict[str, object]]:
    stmt = (
        select(
            Projection.season_year,
            Projection.week,
            func.count(Projection.projection_id),
            func.count(Projection.projected_points),
            func.sum(sql_cast(Projection.projected_stats.is_not(None), Integer)),
        )
        .group_by(Projection.season_year, Projection.week)
        .order_by(Projection.season_year, Projection.week)
    )
    cells: list[dict[str, object]] = []
    for season_year, week, rows, points, stats in session.execute(stmt).all():
        row_count = int(rows or 0)
        points_count = int(points or 0)
        stats_count = int(stats or 0)
        status = "present" if points_count or stats_count else "partial"
        cells.append(
            {
                "season_year": int(season_year),
                "week": int(week),
                "status": status,
                "reason": None if status == "present" else "projection_points_not_scored",
                "row_count": row_count,
                "projected_points_count": points_count,
                "projected_stats_count": stats_count,
            }
        )
    return cells


def _relevance_summary(session: Session) -> dict[str, object]:
    total_players = int(session.execute(select(func.count(Player.player_id))).scalar_one() or 0)
    rostered_ids = {
        int(pid)
        for pid in session.execute(select(TeamRoster.player_id).distinct()).scalars().all()
        if pid is not None
    }
    candidates = _identity_split_candidates(session)
    candidate_member_ids = set()
    for candidate in candidates:
        for member in candidate["members"]:
            candidate_member_ids.add(int(member["player_id"]))
    relevant_ids = rostered_ids | candidate_member_ids
    return {
        "total_players": total_players,
        "league_rostered_players": len(rostered_ids),
        "league_relevant_players": len(relevant_ids),
        "excluded_players": max(total_players - len(relevant_ids), 0),
        "identity_split_candidate_count": len(candidates),
        "identity_split_candidates": candidates,
    }


def _identity_split_candidates(session: Session) -> list[dict[str, Any]]:
    """Detect same-name roster/stat twins without reconciling them."""
    duplicate_names = [
        str(name)
        for name in session.execute(
            select(Player.name_full)
            .group_by(Player.name_full)
            .having(func.count(Player.player_id) > 1)
        ).scalars()
        if name
    ]
    if not duplicate_names:
        return []

    rostered_ids = {
        int(pid)
        for pid in session.execute(select(TeamRoster.player_id).distinct()).scalars().all()
        if pid is not None
    }
    scored_ids = {
        int(pid)
        for pid in session.execute(select(PlayerStatsScored.player_id).distinct()).scalars().all()
        if pid is not None
    }
    injured_ids = {
        int(pid)
        for pid in session.execute(select(PlayerInjuryReport.player_id).distinct()).scalars().all()
        if pid is not None
    }
    linked_member_ids = {
        int(pid)
        for pid in session.execute(select(PlayerIdentityLink.member_player_id)).scalars().all()
        if pid is not None
    }
    players = list(
        session.execute(
            select(
                Player.player_id,
                Player.name_full,
                Player.position,
                Player.nfl_team,
                Player.gsis_id,
                Player.nfl_com_player_id,
            )
            .where(Player.name_full.in_(duplicate_names))
            .order_by(Player.name_full, Player.player_id)
        ).all()
    )
    by_name: dict[str, list[Any]] = {}
    for row in players:
        by_name.setdefault(str(row.name_full), []).append(row)

    out: list[dict[str, Any]] = []
    for name, rows in by_name.items():
        roster_side = [
            r
            for r in rows
            if int(r.player_id) in rostered_ids
            and int(r.player_id) not in scored_ids
            and int(r.player_id) not in injured_ids
        ]
        data_side = [
            r
            for r in rows
            if int(r.player_id) not in rostered_ids
            and int(r.player_id) not in linked_member_ids
            and (int(r.player_id) in scored_ids or int(r.player_id) in injured_ids)
        ]
        if not roster_side or not data_side:
            continue
        roster_positions = {r.position for r in roster_side if r.position is not None}
        if roster_positions:
            data_side = [r for r in data_side if r.position in roster_positions]
        roster_teams = {r.nfl_team for r in roster_side if r.nfl_team is not None}
        if roster_teams:
            data_side = [r for r in data_side if r.nfl_team in roster_teams]
        if not data_side:
            continue
        members: list[dict[str, object]] = []
        for row in roster_side + data_side:
            row = type_cast("Any", row)
            pid = int(row.player_id)
            members.append(
                {
                    "player_id": pid,
                    "name_full": row.name_full,
                    "position": row.position,
                    "nfl_team": row.nfl_team,
                    "gsis_id": row.gsis_id,
                    "nfl_com_player_id": row.nfl_com_player_id,
                    "rostered": pid in rostered_ids,
                    "scored": pid in scored_ids,
                    "injured": pid in injured_ids,
                }
            )
        out.append(
            {
                "name_full": name,
                "reason": "identity_split_candidate",
                "members": members,
            }
        )
    return out
