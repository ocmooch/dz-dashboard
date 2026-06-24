"""Records book / hall of fame superlatives.

Score-based records (team scores, margins, best player week) are computed over
the **scored era** (seasons with ``player_stats_scored``); record-only
superlatives (championships, season points-for, streaks) extend across every
season with standings. Each record carries the context needed to deep-link to
its source. When the data needed for a record is absent, the record is returned
``available: false`` with a reason — never a fake zero.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import (
    Matchup,
    Player,
    PlayerStatsScored,
    Season,
    Team,
    TeamRoster,
)
from sqlalchemy import Float, cast, distinct, func, select

from ff_dashboard.analytics.bracket import season_sacko_map
from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks
from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.head_to_head import closest_rivalry
from ff_dashboard.analytics.historical_team_names import period_team_name_by_slot

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def scored_window(session: Session) -> set[int]:
    """Season ids in the player-scored era (``player_stats_scored`` present)."""
    scored_years = set(seasons_scored(session))
    return {
        int(sid)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
        if int(yr) in scored_years
    }


def team_record_window(session: Session) -> set[int]:
    """Season ids that have team totals — any matchup with a non-null team score.

    Historically wider than :func:`scored_window` when team scores existed for
    seasons before player scoring had been reconstructed. With the reconstruction
    landed (F-51) the real-DB windows now coincide for completed seasons, but the
    split is kept data-driven so the records book stays correct if coverage ever
    diverges again (e.g. a current season with team totals but no scoring yet).
    """
    rows = session.execute(
        select(distinct(Matchup.season_id)).where(Matchup.team_score.is_not(None))
    ).scalars()
    return {int(sid) for sid in rows}


def _team_context(session: Session) -> dict[int, dict[str, Any]]:
    owners = owner_name_map(session)
    rows = session.execute(
        select(Team.team_id, Team.team_name, Team.team_abbrev, Team.owner_id, Team.season_id)
    ).all()
    return {
        int(tid): {
            "team_id": int(tid),
            "team_name": tname,
            "team_abbrev": tabbrev,
            "owner_id": int(oid),
            "owner_name": owners.get(int(oid)),
            "season_id": int(sid),
        }
        for tid, tname, tabbrev, oid, sid in rows
    }


def records_book(session: Session) -> dict[str, Any]:
    """Assemble the full records book."""
    scored = set(seasons_scored(session))
    season_year: dict[int, int] = {
        int(sid): int(yr)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
    }
    # Team/score/margin records span every season with team totals; player-level
    # records stay scoped to the scored era. Both windows are data-driven; with
    # F-51 they coincide on the real DB for completed seasons, but the split
    # holds if a season ever has team totals without per-player scoring.
    team_season_ids = team_record_window(session)
    teams = _team_context(session)

    def ctx(team_id: int, week: int) -> dict[str, Any]:
        c = dict(teams.get(team_id, {"team_id": team_id}))
        sid = c.get("season_id")
        year = season_year.get(sid) if isinstance(sid, int) else None
        c["season_year"] = year
        c["team_name"] = period_team_name_by_slot(year, c.get("team_abbrev"), c.get("team_name"))
        c.pop("team_abbrev", None)
        c["week"] = week
        return c

    matchups = list(
        session.execute(select(Matchup).where(Matchup.season_id.in_(team_season_ids)))
        .scalars()
        .all()
    )

    book: dict[str, Any] = {
        "scored_era": sorted(scored),
        "team_record_era": sorted({season_year[sid] for sid in team_season_ids}),
        "highest_team_score": _unavailable("no_team_data"),
        "lowest_team_score": _unavailable("no_team_data"),
        "biggest_blowout": _unavailable("no_team_data"),
        "narrowest_win": _unavailable("no_team_data"),
        "highest_scoring_matchup": _unavailable("no_team_data"),
        "best_player_week": _unavailable("no_scored_data"),
    }

    # Capture scores as typed floats up front so the arithmetic below is clean
    # (mypy doesn't narrow ORM attributes across calls/comprehensions).
    scored_matchups = [(m, m.team_score) for m in matchups if m.team_score is not None]
    if scored_matchups:
        hi_m, hi_score = max(scored_matchups, key=lambda p: p[1])
        lo_m, lo_score = min(scored_matchups, key=lambda p: p[1])
        book["highest_team_score"] = {
            "available": True,
            "value": round(hi_score, 2),
            "matchup_id": hi_m.matchup_id,
            **ctx(hi_m.team_id, hi_m.week),
        }
        book["lowest_team_score"] = {
            "available": True,
            "value": round(lo_score, 2),
            "matchup_id": lo_m.matchup_id,
            **ctx(lo_m.team_id, lo_m.week),
        }

    decided = [
        (m, m.team_score, m.opponent_score)
        for m in matchups
        if m.team_score is not None and m.opponent_score is not None
    ]

    def win_record(m: Matchup, margin: float) -> dict[str, Any]:
        """A win-margin record carrying *both* sides' season-correct names, so the
        UI can render "<winner> def. <loser>" rather than a bare number."""
        winner = ctx(m.team_id, m.week)
        loser = ctx(m.opponent_team_id, m.week) if m.opponent_team_id is not None else {}
        return {
            "available": True,
            "value": round(margin, 2),
            "matchup_id": m.matchup_id,
            "season_year": winner.get("season_year"),
            "week": m.week,
            # ``winner``/``loser_team_id`` preserved for back-compat; the flat
            # name fields below are what the records grid reads.
            "winner": winner,
            "winner_team_id": m.team_id,
            "winner_name": winner.get("team_name"),
            "winner_owner_name": winner.get("owner_name"),
            "loser_team_id": m.opponent_team_id,
            "loser_name": loser.get("team_name"),
            "loser_owner_name": loser.get("owner_name"),
        }

    wins = [(m, ts - os) for m, ts, os in decided if ts > os]
    if wins:
        blow_m, blow_margin = max(wins, key=lambda p: p[1])
        narrow_m, narrow_margin = min(wins, key=lambda p: p[1])
        book["biggest_blowout"] = win_record(blow_m, blow_margin)
        book["narrowest_win"] = win_record(narrow_m, narrow_margin)

    # Highest-scoring matchup: dedupe to one row per game (team_id < opponent).
    games = [
        (m, ts, os)
        for m, ts, os in decided
        if m.opponent_team_id is not None and m.team_id < m.opponent_team_id
    ]
    if games:
        top_m, top_ts, top_os = max(games, key=lambda p: p[1] + p[2])
        home = ctx(top_m.team_id, top_m.week)
        away = ctx(top_m.opponent_team_id, top_m.week) if top_m.opponent_team_id is not None else {}
        book["highest_scoring_matchup"] = {
            "available": True,
            "value": round(top_ts + top_os, 2),
            "matchup_id": top_m.matchup_id,
            "season_year": season_year.get(top_m.season_id),
            "week": top_m.week,
            "team_id": top_m.team_id,
            "team_name": home.get("team_name"),
            "owner_name": home.get("owner_name"),
            "opponent_team_id": top_m.opponent_team_id,
            "opponent_name": away.get("team_name"),
            "opponent_owner_name": away.get("owner_name"),
            "team_score": round(top_ts, 2),
            "opponent_score": round(top_os, 2),
        }

    # Best player week: the highest single-week score the league actually awarded a
    # *started* player. Two corrections over a naive global ``player_stats_scored``
    # max (which crowned the wrong player — e.g. a 2025 RB over the real record):
    #   1. Scope to rows the league rostered **and started** (``team_rosters``,
    #      ``is_starter``). The nflverse scoring spans the whole NFL, so its global
    #      max can be a player nobody in this league ever started.
    #   2. Score each row the way the box score does — prefer NFL.com's authoritative
    #      ``extra_data.nfl_com_points`` (it carries bonuses the reconstruction
    #      omits, e.g. long-TD), fall back to the reconstruction only when absent.
    # The result is the same number the player's source box score shows.
    nfl_points = cast(func.json_extract(TeamRoster.extra_data, "$.nfl_com_points"), Float)
    started_points = func.coalesce(nfl_points, PlayerStatsScored.total_points)
    best_player = session.execute(
        select(
            TeamRoster.team_id,
            TeamRoster.player_id,
            TeamRoster.week,
            Player.name_full,
            Player.position,
            started_points.label("points"),
        )
        .join(Player, Player.player_id == TeamRoster.player_id)
        .join(Season, Season.year == TeamRoster.season_year)
        .outerjoin(
            PlayerStatsScored,
            (PlayerStatsScored.player_id == TeamRoster.player_id)
            & (PlayerStatsScored.season_id == Season.season_id)
            & (PlayerStatsScored.week == TeamRoster.week),
        )
        .where(TeamRoster.is_starter.is_(True))
        .where(started_points.is_not(None))
        .order_by(started_points.desc())
        .limit(1)
    ).first()
    if best_player is not None:
        c = ctx(int(best_player.team_id), int(best_player.week))
        book["best_player_week"] = {
            "available": True,
            "value": round(float(best_player.points), 2),
            "player_id": int(best_player.player_id),
            "player_name": best_player.name_full,
            "position": best_player.position,
            "team_id": c.get("team_id"),
            "team_name": c.get("team_name"),
            "owner_id": c.get("owner_id"),
            "owner_name": c.get("owner_name"),
            "season_year": c.get("season_year"),
            "week": int(best_player.week),
        }

    book.update(_record_only(session, teams, season_year))

    # The "closest rivalry" — most-played pair nearest a 50/50 split (04 §4). A
    # records-book stat that deep-links to its pairwise page on the frontend.
    rivalry = closest_rivalry(session)
    book["closest_rivalry"] = (
        {"available": True, **rivalry} if rivalry is not None else _unavailable("no_meetings")
    )
    return book


def _record_only(
    session: Session, teams: dict[int, dict[str, Any]], season_year: dict[int, int]
) -> dict[str, Any]:
    """Records that don't need scored data: championships, season PF, streaks."""
    owners = owner_name_map(session)

    # Most championships.
    champ_counts: dict[int, int] = {}
    for season in session.execute(select(Season)).scalars().all():
        if season.champion_team_id is not None:
            owner_id = teams.get(season.champion_team_id, {}).get("owner_id")
            if owner_id is not None:
                champ_counts[owner_id] = champ_counts.get(owner_id, 0) + 1
    most_champs: dict[str, Any]
    if champ_counts:
        owner_id, n = max(champ_counts.items(), key=lambda kv: kv[1])
        most_champs = {
            "available": True,
            "value": n,
            "owner_id": owner_id,
            "owner_name": owners.get(owner_id),
        }
    else:
        most_champs = _unavailable("no_champions")

    # Most Sackos — the anti-championship. The toilet-bowl loser per season, owner-keyed.
    sacko_counts: dict[int, int] = {}
    for sacko in season_sacko_map(session).values():
        owner_id = sacko.get("owner_id")
        if owner_id is not None:
            sacko_counts[owner_id] = sacko_counts.get(owner_id, 0) + 1
    most_sackos: dict[str, Any]
    if sacko_counts:
        owner_id, n = max(sacko_counts.items(), key=lambda kv: kv[1])
        most_sackos = {
            "available": True,
            "value": n,
            "owner_id": owner_id,
            "owner_name": owners.get(owner_id),
        }
    else:
        most_sackos = _unavailable("no_sackos")

    # Best / worst single-season regular-season points-for, from matchups.
    from ff_dashboard.analytics.owners import _standings_index

    index = _standings_index(session)
    best_pf: dict[str, Any] = _unavailable("no_standings")
    worst_pf: dict[str, Any] = _unavailable("no_standings")
    if index:
        best = max(index.values(), key=lambda r: r["points_for"])
        worst = min(index.values(), key=lambda r: r["points_for"])
        best_pf = {
            "available": True,
            "value": best["points_for"],
            "team_id": best["team_id"],
            "team_name": best["team_name"],
            "owner_id": best["owner_id"],
            "owner_name": best["owner_name"],
            "season_year": best["season_year"],
        }
        worst_pf = {
            "available": True,
            "value": worst["points_for"],
            "team_id": worst["team_id"],
            "team_name": worst["team_name"],
            "owner_id": worst["owner_id"],
            "owner_name": worst["owner_name"],
            "season_year": worst["season_year"],
        }

    win_streak, loss_streak = _longest_streaks(session, owners, season_year)

    return {
        "most_championships": most_champs,
        "most_sackos": most_sackos,
        "best_season_points_for": best_pf,
        "worst_season_points_for": worst_pf,
        "longest_win_streak": win_streak,
        "longest_loss_streak": loss_streak,
    }


def _longest_streaks(
    session: Session, owners: dict[int, str | None], season_year: dict[int, int]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Longest cross-season W and L streaks per owner (regular season)."""
    from ff_dashboard.analytics.common import team_owner_map

    owner_of = team_owner_map(session)
    reg_by_season = {
        s.season_id: regular_season_weeks(session, s)
        for s in session.execute(select(Season)).scalars().all()
    }
    matchups = list(session.execute(select(Matchup)).scalars().all())
    # owner_id -> ordered (year, week, result)
    per_owner: dict[int, list[tuple[int, int, str]]] = {}
    for m in matchups:
        reg = reg_by_season.get(m.season_id, 0)
        if m.week > reg:
            continue
        owner_id = owner_of.get(m.team_id)
        if owner_id is None:
            continue
        if m.is_win is True:
            res = "W"
        elif m.is_win is False:
            res = "L"
        else:
            continue
        per_owner.setdefault(owner_id, []).append((season_year.get(m.season_id, 0), m.week, res))

    best_w: tuple[int, int] | None = None  # (length, owner_id)
    best_l: tuple[int, int] | None = None
    for owner_id, seq in per_owner.items():
        seq.sort()
        cur_w = cur_l = 0
        for _, _, res in seq:
            cur_w = cur_w + 1 if res == "W" else 0
            cur_l = cur_l + 1 if res == "L" else 0
            if best_w is None or cur_w > best_w[0]:
                best_w = (cur_w, owner_id)
            if best_l is None or cur_l > best_l[0]:
                best_l = (cur_l, owner_id)

    def pack(best: tuple[int, int] | None, reason: str) -> dict[str, Any]:
        if best is None or best[0] == 0:
            return _unavailable(reason)
        return {
            "available": True,
            "value": best[0],
            "owner_id": best[1],
            "owner_name": owners.get(best[1]),
        }

    return pack(best_w, "no_games"), pack(best_l, "no_games")


def championships(session: Session) -> dict[str, Any]:
    """Championship history / dynasty timeline, one entry per season."""
    teams = _team_context(session)
    owners = owner_name_map(session)

    def label(team_id: int | None, year: int) -> dict[str, Any] | None:
        if team_id is None:
            return None
        t = teams.get(team_id, {})
        return {
            "team_id": team_id,
            # The DB's team_name carries the latest canonical label after
            # owner-identity repair; render the season-correct slot name.
            "team_name": period_team_name_by_slot(year, t.get("team_abbrev"), t.get("team_name")),
            "owner_id": t.get("owner_id"),
            "owner_name": owners.get(t.get("owner_id", -1)),
        }

    sacko_map = season_sacko_map(session)
    entries: list[dict[str, Any]] = []
    for season in session.execute(select(Season).order_by(Season.year)).scalars().all():
        sacko = sacko_map.get(int(season.season_id))
        sacko_ref = label(sacko["team_id"], season.year) if sacko else None
        entries.append(
            {
                "season_year": season.year,
                "champion": label(season.champion_team_id, season.year),
                "runner_up": label(season.runner_up_team_id, season.year),
                "last_place": label(season.last_place_team_id, season.year),
                # The Sacko (toilet-bowl loser) — derived from the bracket where it
                # can be distinguished, else the recorded last-place team. ``source``
                # lets the UI caveat the recorded fallback.
                "sacko": {**sacko_ref, "source": sacko["source"]} if sacko_ref and sacko else None,
            }
        )
    return {"seasons": entries}
