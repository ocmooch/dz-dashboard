"""Derived roster-diff fallback moves (``analytics/transactions.py``).

The Phase-1 ``Transaction`` table now carries the exact activity log where the
upstream scrape has rows. This module remains useful as a fallback/estimate from
``team_rosters`` snapshots: week-over-week diffs reconstruct the **shape** of
activity — adds, drops, and retained players — even when exact rows are absent.

Fallback only: this derives *what changed and when* by fantasy week, not the
exact calendar date, waiver-vs-FA classification, or FAAB bid. Prefer
``team_transactions`` when exact recorded rows exist.

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
from ff_dashboard.analytics.roster_snapshots import is_reconstructed_week, snapshot_kind

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def derive_roster_moves(session: Session, team_id: int) -> dict[str, Any] | None:
    """In-season add/drop/retain derived from week-over-week ``team_rosters`` diffs.

    Fallback (dashboard, read-only): the *shape* of activity only — no exact
    dates / waiver-vs-FA / FAAB bids.
    Returns ``None`` for an unknown ``team_id`` (404).

    A player drafted at the opening roster week and kept all season is a
    ``retain`` (never a spurious ``add``); a player first seen after the opening
    week is an ``add``; a player who disappears between snapshots is a ``drop`` at
    the week they are gone. Drop-then-readd yields a ``drop`` then a fresh ``add``
    (the stint model). With fewer than two snapshot weeks churn cannot be derived,
    so ``available`` is ``False`` (the UI renders a ``DataGap``, never zeros).

    Weeks whose whole roster is a reconstructed *audit* snapshot are **excluded
    from the diff** (and reported in ``reconstructed_weeks``): their attribution
    is non-authoritative, so diffing against one fabricates a churn burst at the
    audit↔history boundary — every player the audit roster disagrees with would
    look added or dropped. See ``analytics/roster_snapshots``.
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

    # Drop reconstructed (all-audit) weeks before diffing — see docstring.
    week_kinds: dict[int, list[str | None]] = defaultdict(list)
    for r, _ in rows:
        week_kinds[int(r.week)].append(snapshot_kind(r))
    reconstructed_weeks = sorted(
        w for w, kinds in week_kinds.items() if is_reconstructed_week(kinds)
    )
    reconstructed_set = set(reconstructed_weeks)

    roster_weeks = sorted({int(r.week) for r, _ in rows} - reconstructed_set)
    present: dict[int, set[int]] = defaultdict(set)
    players: dict[int, Player] = {}
    for r, p in rows:
        week = int(r.week)
        if week in reconstructed_set:
            continue
        present[p.player_id].add(week)
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
        "reconstructed_weeks": reconstructed_weeks,
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
