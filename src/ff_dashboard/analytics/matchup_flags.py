"""Matchup superlative flags (``analytics/matchup_flags.py``).

A *flag* is a superlative — an at-a-glance signal of what made a game memorable,
not a bare margin. The same flag list feeds both the weekly grid
(:func:`ff_dashboard.analytics.matchups.week_matchups`) and the individual box
score (:func:`ff_dashboard.analytics.matchups.box_score`), so the two views never
disagree. All thresholds and rules live here (backend) so "no metric math in web"
holds — the SPA only renders the returned ``{kind, label, tone, team_id, detail}``.

Every rule uses **durable** inputs only: authoritative team scores, margins,
entering W-L records, and ``player_stats_scored`` (2010-2025). Projection-derived
flags were deliberately excluded — projection coverage is not consistent across
seasons/playoffs.

Flag kinds:

* ``blowout`` / ``nailbiter`` — game-local margin extremes.
* ``season_high`` / ``dud`` — a team's score is the season's highest / lowest.
* ``shootout`` / ``cold_snap`` — combined score is the season's highest / coldest.
* ``tough_luck`` — the loser outscored every other team that played that week.
* ``upset`` — the winner entered with a clearly worse record than the loser.
* ``monster_game`` — the game held one of the season's top individual starter weeks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Player, PlayerStatsScored, TeamRoster
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Tunable thresholds. Kept backend-side; the frontend reads the resulting flags.
CLOSE_MARGIN = 5.0  # nailbiter: a decided game within 5 points
BLOWOUT_MARGIN = 40.0  # blowout: a margin of 40+ points
UPSET_RECORD_GAP = 3  # upset: loser entered with >= this many more wins than the winner
MIN_ENTERING_GAMES = 3  # ignore upset/record gaps before each side has played this many
MONSTER_TOP_N = 3  # a game is a "monster game" if it held one of the top-N starter weeks


def season_score_context(session: Session, season_id: int, season_year: int) -> dict[str, Any]:
    """Per-season extremes used by the season/player flags.

    One pass over the season's matchups (byes excluded from team-score extremes,
    games deduped for combined-score extremes) plus a small top-N starter-week
    query. Computed once per ``week_matchups`` / ``box_score`` call and reused for
    every game; the callers are themselves cached per (season, week) / matchup.
    """
    rows = list(
        session.execute(select(Matchup).where(Matchup.season_id == season_id)).scalars().all()
    )

    # Single-team extremes: only real games (a bye is not a "low score" superlative).
    team_scores = [
        m.team_score for m in rows if m.team_score is not None and m.opponent_team_id is not None
    ]

    # Combined extremes: one row per game (Phase 1 stores each game twice).
    combined: list[float] = []
    seen: set[frozenset[int]] = set()
    for m in rows:
        if m.team_score is None or m.opponent_score is None or m.opponent_team_id is None:
            continue
        pair = frozenset({m.team_id, m.opponent_team_id})
        if pair in seen:
            continue
        seen.add(pair)
        combined.append(m.team_score + m.opponent_score)

    return {
        "max_team_score": max(team_scores, default=None),
        "min_team_score": min(team_scores, default=None),
        "max_combined": max(combined, default=None),
        "min_combined": min(combined, default=None),
        "monster_team_weeks": _top_starter_weeks(session, season_id, season_year),
    }


def _top_starter_weeks(
    session: Session, season_id: int, season_year: int, n: int = MONSTER_TOP_N
) -> list[dict[str, Any]]:
    """The season's top-N individual *starter* player-weeks, each tied to the
    fantasy team that started the player (so a flag can attach to a side)."""
    rows = session.execute(
        select(
            TeamRoster.team_id,
            TeamRoster.week,
            Player.name_full,
            PlayerStatsScored.total_points,
        )
        .select_from(PlayerStatsScored)
        .join(
            TeamRoster,
            (TeamRoster.player_id == PlayerStatsScored.player_id)
            & (TeamRoster.week == PlayerStatsScored.week)
            & (TeamRoster.season_year == season_year),
        )
        .join(Player, Player.player_id == PlayerStatsScored.player_id)
        .where(
            PlayerStatsScored.season_id == season_id,
            PlayerStatsScored.total_points.is_not(None),
            TeamRoster.is_starter.is_(True),
        )
        .order_by(PlayerStatsScored.total_points.desc())
        .limit(n)
    ).all()
    return [
        {
            "team_id": int(r.team_id),
            "week": int(r.week),
            "player_name": r.name_full,
            "points": round(float(r.total_points), 2),
        }
        for r in rows
    ]


def week_score_context(session: Session, season_id: int, week: int) -> dict[int, float]:
    """Each team's score that week, keyed by ``team_id`` — drives ``tough_luck``."""
    rows = session.execute(
        select(Matchup.team_id, Matchup.team_score).where(
            Matchup.season_id == season_id, Matchup.week == week
        )
    ).all()
    return {int(tid): float(ts) for tid, ts in rows if ts is not None}


def _flag(
    kind: str,
    label: str,
    tone: str,
    *,
    team_id: int | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    return {"kind": kind, "label": label, "tone": tone, "team_id": team_id, "detail": detail}


def _n(x: float) -> str:
    return f"{x:.1f}"


def _rec(r: dict[str, int]) -> str:
    w, ls, t = r.get("wins", 0), r.get("losses", 0), r.get("ties", 0)
    return f"{w}-{ls}" + (f"-{t}" if t else "")


def _eq(a: float | None, b: float | None) -> bool:
    """Two team scores are the same superlative when they round equal (the values
    come from the same column, so this is exact in practice; rounding guards FP)."""
    return a is not None and b is not None and round(a, 2) == round(b, 2)


def flags_for_game(
    *,
    team_a: dict[str, Any] | None,
    team_b: dict[str, Any] | None,
    winner_team_id: int | None,
    margin: float | None,
    week: int,
    season_ctx: dict[str, Any],
    week_ctx: dict[int, float],
) -> list[dict[str, Any]]:
    """Superlative flags for one game. Pure: all DB work is in the contexts.

    ``team_a`` / ``team_b`` are side dicts carrying ``team_id``, ``score`` and
    ``entering_record`` (the shapes ``week_matchups`` and ``box_score`` already
    build). Returns ``[]`` for an unscored or bye game.
    """
    flags: list[dict[str, Any]] = []
    a, b = team_a, team_b
    sa = a["score"] if a else None
    sb = b["score"] if b else None

    # Game-local margin extremes (need a decided, two-sided game).
    if margin is not None and a and b and winner_team_id is not None:
        if margin >= BLOWOUT_MARGIN:
            flags.append(_flag("blowout", "Blowout", "loss", detail=f"{_n(margin)}-point margin"))
        elif margin <= CLOSE_MARGIN:
            flags.append(
                _flag("nailbiter", "Nailbiter", "accent", detail=f"decided by {_n(margin)}")
            )

    # Season single-team extremes (one-sided).
    for side in (a, b):
        if side is None or side["score"] is None:
            continue
        s = side["score"]
        if _eq(s, season_ctx["max_team_score"]):
            flags.append(
                _flag(
                    "season_high",
                    "Season high",
                    "win",
                    team_id=side["team_id"],
                    detail=f"{_n(s)} — season's highest team score",
                )
            )
        if _eq(s, season_ctx["min_team_score"]):
            flags.append(
                _flag(
                    "dud",
                    "Dud",
                    "muted",
                    team_id=side["team_id"],
                    detail=f"{_n(s)} — season's lowest team score",
                )
            )

    # Combined-score extremes (whole game).
    if sa is not None and sb is not None:
        combined = sa + sb
        if _eq(combined, season_ctx["max_combined"]):
            flags.append(
                _flag(
                    "shootout",
                    "Shootout",
                    "accent",
                    detail=f"{_n(combined)} combined — season's highest",
                )
            )
        if _eq(combined, season_ctx["min_combined"]):
            flags.append(
                _flag(
                    "cold_snap",
                    "Cold snap",
                    "muted",
                    detail=f"{_n(combined)} combined — season's coldest",
                )
            )

    # Tough-luck loss: the loser would have beaten every other team that week.
    if winner_team_id is not None and a and b and sa is not None and sb is not None:
        loser = b if winner_team_id == a["team_id"] else a
        ls = loser["score"]
        others = [sc for tid, sc in week_ctx.items() if tid not in (a["team_id"], b["team_id"])]
        if ls is not None and others and ls > max(others):
            flags.append(
                _flag(
                    "tough_luck",
                    "Tough luck",
                    "warn",
                    team_id=loser["team_id"],
                    detail=f"{_n(ls)} — would have beaten every other team this week",
                )
            )

    # Upset: winner entered with a clearly worse record than the loser.
    if winner_team_id is not None and a and b:
        winner = a if winner_team_id == a["team_id"] else b
        loser = b if winner is a else a
        wr = winner.get("entering_record") or {}
        lr = loser.get("entering_record") or {}
        w_games = wr.get("wins", 0) + wr.get("losses", 0) + wr.get("ties", 0)
        l_games = lr.get("wins", 0) + lr.get("losses", 0) + lr.get("ties", 0)
        if (
            w_games >= MIN_ENTERING_GAMES
            and l_games >= MIN_ENTERING_GAMES
            and lr.get("wins", 0) - wr.get("wins", 0) >= UPSET_RECORD_GAP
        ):
            flags.append(
                _flag(
                    "upset",
                    "Upset",
                    "accent",
                    team_id=winner["team_id"],
                    detail=f"{_rec(wr)} beat {_rec(lr)}",
                )
            )

    # Monster game: the game held one of the season's top starter performances.
    game_team_ids = {t["team_id"] for t in (a, b) if t}
    for mw in season_ctx["monster_team_weeks"]:
        if mw["week"] == week and mw["team_id"] in game_team_ids:
            flags.append(
                _flag(
                    "monster_game",
                    "Monster game",
                    "win",
                    team_id=mw["team_id"],
                    detail=f"{mw['player_name']} {_n(mw['points'])} — top performance of the season",
                )
            )

    return flags
