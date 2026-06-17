"""Power ranking + power-over-time (``analytics/power.py``).

A model-driven ranking distinct from raw standings: it rewards strong, consistent
scoring rather than win/loss luck. The model is deliberately simple and legible
(this is *not* Phase 3 prediction) — three within-season z-scores combined by
fixed, documented weights:

```
power_score = 0.40 * z(points_for_per_game)
            + 0.25 * z(all_play_win_pct)
            + 0.20 * z(win_pct)
            + 0.15 * z(points_for_last_3_weeks_per_game)
```

``z(...)`` is the population z-score across that season's teams; a team with no
spread among its peers (or a season with one team) contributes 0, never a
division error. Teams are ranked by ``power_score`` descending.

Every row also carries the team's plain standings rank (wins → points-for, the
same basis the standings timeline climbs by) and ``rank_delta`` = standings_rank
minus power_rank, so the UI can show who the model rates above or below their record
("risers" and "fallers" — the Home top-movers strip).

Inputs come from ``matchups.team_score`` (the authoritative team total) and the
win record, both of which exist for every season with reconstructed team totals.
The model does not need player-level scoring.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup
from ff_pipeline.repository.queries import get_season
from sqlalchemy import func, select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks
from ff_dashboard.analytics.standings import all_play_index, compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# The model weights live in one place and travel to the UI in the payload.
W_POINTS_FOR = 0.4
W_ALL_PLAY = 0.25
W_WIN_PCT = 0.2
W_RECENT = 0.15

# "Recent form" window for the third term (the last N regular-season weeks).
RECENT_WEEKS = 3

POWER_EXPLAINER = (
    "Power score blends four within-season z-scores (each team measured against "
    f"its peers that year): {W_POINTS_FOR:g} x points-for per game, {W_ALL_PLAY:g} x "
    f"all-play win pct, {W_WIN_PCT:g} x actual win pct, and {W_RECENT:g} x "
    f"points-for per game over the last {RECENT_WEEKS} weeks. All-play compares "
    "each team's weekly score against every other team that week, so the model "
    "rewards schedule-resistant scoring without needing player-level data. "
    "Points-for, all-play, and recent form all track scoring, so this is really a "
    "points-dominant lens on the season — a way to re-sort the table by strength and "
    "see who over- or under-performs their record, not a prediction."
)

POWER_WEIGHTS = {
    "points_for_per_game": W_POINTS_FOR,
    "all_play_win_pct": W_ALL_PLAY,
    "win_pct": W_WIN_PCT,
    "recent_points_for_per_game": W_RECENT,
}


def _zscores(values: list[float]) -> list[float]:
    """Population z-scores; all-zeros when there is no spread (or <2 teams)."""
    if len(values) < 2:
        return [0.0] * len(values)
    mean = statistics.mean(values)
    sd = statistics.pstdev(values)
    if sd == 0:
        return [0.0] * len(values)
    return [(v - mean) / sd for v in values]


def _recent_pf(
    session: Session, season_id: int, lower: int, upper: int
) -> dict[int, tuple[float, int]]:
    """``team_id -> (points_for, games)`` over weeks ``lower..upper`` (played, non-bye)."""
    rows = session.execute(
        select(
            Matchup.team_id,
            func.sum(Matchup.team_score),
            func.count(Matchup.matchup_id),
        )
        .where(
            Matchup.season_id == season_id,
            Matchup.week >= lower,
            Matchup.week <= upper,
            Matchup.team_score.is_not(None),
            Matchup.opponent_team_id.is_not(None),
        )
        .group_by(Matchup.team_id)
    ).all()
    return {int(tid): (float(pf or 0.0), int(games)) for tid, pf, games in rows}


def power_ranking(
    session: Session, season_id: int, through_week: int | None = None
) -> dict[str, Any] | None:
    """Power ranking for a season (optionally as-of a week). ``None`` if no season."""
    season = get_season(session, season_id)
    if season is None:
        return None

    standings = compute_standings(session, season_id, through_week)
    if standings is None:  # pragma: no cover - season existence already checked
        return None
    base_rows = standings["rows"]
    upper = standings["through_week"]
    reg_weeks = standings["regular_season_weeks"]
    owners = owner_name_map(session)

    if not base_rows:
        return {
            "season_id": season_id,
            "season_year": season.year,
            "through_week": upper,
            "regular_season_weeks": reg_weeks,
            "weights": POWER_WEIGHTS,
            "explainer": POWER_EXPLAINER,
            "rows": [],
        }

    lower = max(1, upper - RECENT_WEEKS + 1)
    recent = _recent_pf(session, season_id, lower, upper)
    all_play = all_play_index(session, season_id, upper)

    pf_per_game: list[float] = []
    all_play_win_pct: list[float] = []
    win_pct: list[float] = []
    recent_per_game: list[float] = []
    for r in base_rows:
        games = r["wins"] + r["losses"] + r["ties"]
        pf_per_game.append(r["points_for"] / games if games else 0.0)
        all_play_win_pct.append(float(all_play.get(r["team_id"], {}).get("win_pct", 0.0)))
        win_pct.append(r["win_pct"])
        rp, rg = recent.get(r["team_id"], (0.0, 0))
        recent_per_game.append(rp / rg if rg else 0.0)

    z_pf = _zscores(pf_per_game)
    z_all_play = _zscores(all_play_win_pct)
    z_win = _zscores(win_pct)
    z_recent = _zscores(recent_per_game)

    rows: list[dict[str, Any]] = []
    for i, r in enumerate(base_rows):
        score = (
            W_POINTS_FOR * z_pf[i]
            + W_ALL_PLAY * z_all_play[i]
            + W_WIN_PCT * z_win[i]
            + W_RECENT * z_recent[i]
        )
        rows.append(
            {
                "team_id": r["team_id"],
                "team_name": r["team_name"],
                "owner_id": r["owner_id"],
                "owner_name": owners.get(r["owner_id"]),
                "wins": r["wins"],
                "losses": r["losses"],
                "ties": r["ties"],
                "points_for": r["points_for"],
                "power_score": round(score, 4),
                "points_for_per_game": round(pf_per_game[i], 2),
                "all_play_win_pct": round(all_play_win_pct[i], 4),
                "win_pct": r["win_pct"],
                "recent_points_for_per_game": round(recent_per_game[i], 2),
                "z_points_for": round(z_pf[i], 4),
                "z_all_play_win_pct": round(z_all_play[i], 4),
                "z_win_pct": round(z_win[i], 4),
                "z_recent": round(z_recent[i], 4),
            }
        )

    # Standings rank (wins -> points-for) for the model-vs-record comparison.
    for rank, r in enumerate(sorted(rows, key=lambda x: (-x["wins"], -x["points_for"])), start=1):
        r["standings_rank"] = rank

    rows.sort(key=lambda x: -x["power_score"])
    for rank, r in enumerate(rows, start=1):
        r["rank"] = rank
        r["rank_delta"] = r["standings_rank"] - rank

    return {
        "season_id": season_id,
        "season_year": season.year,
        "through_week": upper,
        "regular_season_weeks": reg_weeks,
        "weights": POWER_WEIGHTS,
        "explainer": POWER_EXPLAINER,
        "rows": rows,
    }


def power_timeline(session: Session, season_id: int) -> dict[str, Any] | None:
    """Power rank + power score per team per regular-season week (the RankFlow)."""
    season = get_season(session, season_id)
    if season is None:
        return None
    reg_weeks = regular_season_weeks(session, season)
    owners = owner_name_map(session)

    series: dict[int, dict[str, Any]] = {}
    for week in range(1, reg_weeks + 1):
        snap = power_ranking(session, season_id, through_week=week)
        if snap is None:  # pragma: no cover - season existence already checked
            continue
        for r in snap["rows"]:
            team = series.setdefault(
                r["team_id"],
                {
                    "team_id": r["team_id"],
                    "team_name": r["team_name"],
                    "owner_id": r["owner_id"],
                    "owner_name": owners.get(r["owner_id"]),
                    "points": [],
                },
            )
            team["points"].append(
                {"week": week, "rank": r["rank"], "power_score": r["power_score"]}
            )

    return {
        "season_id": season_id,
        "season_year": season.year,
        "regular_season_weeks": reg_weeks,
        "teams": list(series.values()),
    }
