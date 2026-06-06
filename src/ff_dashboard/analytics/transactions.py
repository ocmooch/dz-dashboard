"""Derived in-season roster moves (``analytics/transactions.py``).

The Phase-1 ``Transaction`` table is draft-only on the real DB (F-37), so it
cannot show in-season waiver/add-drop activity. ``team_rosters`` *is* week-grained,
though, so week-over-week diffs reconstruct the **shape** of that activity —
adds, drops, and retained players — with no nfl.com scrape.

Tier-1 only: this derives *what changed and when* (by fantasy week), not the
exact calendar date, waiver-vs-FA classification, or FAAB bid — those need the
nfl.com transaction feed and are deferred to the upstream program (F-37 tier 2).

Moves are **not** gated on ``is_scored``: roster snapshots exist for the unscored
(pre-reconstruction) seasons too, so add/drop shape is available even where
per-player *points* are not.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Player, TeamRoster
from ff_pipeline.repository.queries import get_season, get_team
from sqlalchemy import select

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.coverage import seasons_scored

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def derive_roster_moves(session: Session, team_id: int) -> dict[str, Any] | None:
    """In-season add/drop/retain derived from week-over-week ``team_rosters`` diffs.

    Tier-1 (dashboard, read-only): the *shape* of activity only — no nfl.com
    scrape, no exact dates / waiver-vs-FA / FAAB bids (those are UP, F-37 tier 2).
    Returns ``None`` for an unknown ``team_id`` (404).

    A player drafted at the opening roster week and kept all season is a
    ``retain`` (never a spurious ``add``); a player first seen after the opening
    week is an ``add``; a player who disappears between snapshots is a ``drop`` at
    the week they are gone. Drop-then-readd yields a ``drop`` then a fresh ``add``
    (the stint model). With fewer than two snapshot weeks churn cannot be derived,
    so ``available`` is ``False`` (the UI renders a ``DataGap``, never zeros).
    """
    require_league(session)  # 503 when the pipeline has never run
    team = get_team(session, team_id)
    if team is None:
        return None
    season = get_season(session, team.season_id)
    if season is None:  # pragma: no cover - a team always has its season
        return None

    rows = session.execute(
        select(TeamRoster, Player)
        .join(Player, Player.player_id == TeamRoster.player_id)
        .where(TeamRoster.team_id == team_id)
    ).all()

    roster_weeks = sorted({int(r.week) for r, _ in rows})
    present: dict[int, set[int]] = defaultdict(set)
    players: dict[int, Player] = {}
    for r, p in rows:
        present[p.player_id].add(int(r.week))
        players[p.player_id] = p

    is_scored = season.year in set(seasons_scored(session))
    available = len(roster_weeks) >= 2

    moves: list[dict[str, Any]] = []
    if available:
        first_week, last_week = roster_weeks[0], roster_weeks[-1]
        for pid, weeks_present in present.items():
            player = players[pid]
            # Drafted-and-kept: present at every snapshot week → one retain.
            if all(w in weeks_present for w in roster_weeks):
                moves.append(_move(first_week, player, "retain"))
                continue
            # Otherwise walk the snapshots, emitting an add at each (re-)entry
            # after the opening week and a drop at each disappearance.
            for i, w in enumerate(roster_weeks):
                here = w in weeks_present
                prev_here = i > 0 and roster_weeks[i - 1] in weeks_present
                if here and w != first_week and not prev_here:
                    moves.append(_move(w, player, "add"))
                if here and w != last_week and roster_weeks[i + 1] not in weeks_present:
                    moves.append(_move(roster_weeks[i + 1], player, "drop"))

    moves.sort(key=lambda m: (m["week"], m["action"], m["player_name"] or ""))

    return {
        "team_id": team_id,
        "season_year": season.year,
        "is_scored": is_scored,
        "available": available,
        "roster_weeks": roster_weeks,
        "moves": moves,
    }


def _move(week: int, player: Player, action: str) -> dict[str, Any]:
    return {
        "week": week,
        "player_id": player.player_id,
        "player_name": player.name_full,
        "position": player.position,
        "action": action,
    }
