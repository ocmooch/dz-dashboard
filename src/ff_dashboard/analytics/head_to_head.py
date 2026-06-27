"""Head-to-head records and the rivalry matrix.

Keyed on **owners**, not teams, so records span team renames and seasons. Two
traps this module is written to avoid:

* **Two matchup rows per game.** Each game is stored once per team. We dedupe by
  processing only the row whose team's owner id is the lower of the pair, so
  every game is counted exactly once with both scores in hand.
* **Byes.** Rows with no opponent are excluded from counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Season
from sqlalchemy import select

from ff_dashboard.analytics.bracket import (
    TIER_CHAMPIONSHIP,
    TIER_CONSOLATION,
    postseason_classification,
)
from ff_dashboard.analytics.common import (
    owner_active_map,
    owner_name_map,
    owner_prominence_map,
    team_owner_map,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

Pair = tuple[int, int]  # (lower_owner_id, higher_owner_id)

# A pair below this many meetings is too thin to crown as a "dead-even" rivalry —
# a lone 1-1 split is not a 50/50 series. Mirrors rivalries.MIN_INTENSITY_GAMES.
MIN_DEAD_EVEN_GAMES = 4


def _blank_pair() -> dict[str, Any]:
    return {
        "games": 0,
        "low_wins": 0,  # wins for the lower-id owner
        "high_wins": 0,
        "ties": 0,
        "low_margin_total": 0.0,  # signed margin from the lower-id owner's view
        # ``playoff_meetings`` counts **true** (non-consolation) playoff games only;
        # consolation/"toilet" games are tracked separately and never inflate it.
        "playoff_meetings": 0,
        "consolation_meetings": 0,
        "meetings": [],
    }


def all_pairwise(session: Session) -> dict[Pair, dict[str, Any]]:
    """Aggregate every owner-vs-owner meeting, deduped to one row per game."""
    owner_of = team_owner_map(session)
    season_year: dict[int, int] = {
        int(sid): int(yr)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
    }

    pairs: dict[Pair, dict[str, Any]] = {}
    # One postseason classification per season, shared across every meeting so
    # consolation games stop counting as true playoff meetings (the bracket split
    # lives in bracket.py; see postseason_classification).
    class_cache: dict[int, dict[str, Any]] = {}

    def tier_for(m: Matchup) -> str | None:
        if not m.is_playoff:
            return None
        cls = class_cache.get(m.season_id)
        if cls is None:
            cls = postseason_classification(session, m.season_id)
            class_cache[m.season_id] = cls
        entry = cls["by_matchup_id"].get(m.matchup_id)
        return entry["tier"] if entry is not None else None

    rows = (
        session.execute(select(Matchup).where(Matchup.opponent_team_id.is_not(None)))
        .scalars()
        .all()
    )
    for m in rows:
        a_owner = owner_of.get(m.team_id)
        b_owner = owner_of.get(m.opponent_team_id) if m.opponent_team_id is not None else None
        if a_owner is None or b_owner is None or a_owner == b_owner:
            continue
        # Count each game once: only the row whose owner is the lower id.
        if a_owner > b_owner:
            continue
        if m.team_score is None or m.opponent_score is None:
            continue

        key: Pair = (a_owner, b_owner)
        agg = pairs.setdefault(key, _blank_pair())
        agg["games"] += 1
        margin = m.team_score - m.opponent_score  # low owner's signed margin
        agg["low_margin_total"] += margin
        if margin > 0:
            agg["low_wins"] += 1
        elif margin < 0:
            agg["high_wins"] += 1
        else:
            agg["ties"] += 1
        tier = tier_for(m)
        is_consolation = tier == TIER_CONSOLATION
        is_championship = tier == TIER_CHAMPIONSHIP
        # True playoff = a postseason game that is not consolation. Where the bracket
        # can't be distinguished (tier is None) we keep the prior behaviour rather
        # than guess — an indistinguishable game still counts as playoff.
        is_true_playoff = bool(m.is_playoff) and not is_consolation
        if is_true_playoff:
            agg["playoff_meetings"] += 1
        if is_consolation:
            agg["consolation_meetings"] += 1
        agg["meetings"].append(
            {
                "matchup_id": m.matchup_id,
                "season_id": m.season_id,
                "season_year": season_year.get(m.season_id),
                "week": m.week,
                "low_score": m.team_score,
                "high_score": m.opponent_score,
                "low_margin": margin,
                "is_playoff": m.is_playoff,
                "bracket_tier": tier,
                "is_true_playoff": is_true_playoff,
                "is_championship": is_championship,
                "is_consolation": is_consolation,
            }
        )
    return pairs


def pairwise_record(session: Session, owner_a: int, owner_b: int) -> dict[str, Any]:
    """All-time record between two owners, oriented to ``owner_a``."""
    names = owner_name_map(session)
    base = {
        "owner_a": {"owner_id": owner_a, "display_name": names.get(owner_a)},
        "owner_b": {"owner_id": owner_b, "display_name": names.get(owner_b)},
    }
    if owner_a == owner_b:
        return {**base, "available": False, "reason": "same_owner", "games_played": 0}

    low, high = (owner_a, owner_b) if owner_a < owner_b else (owner_b, owner_a)
    agg = all_pairwise(session).get((low, high))
    if agg is None or agg["games"] == 0:
        return {**base, "available": False, "reason": "no_meetings", "games_played": 0}

    a_is_low = owner_a == low
    a_wins = agg["low_wins"] if a_is_low else agg["high_wins"]
    b_wins = agg["high_wins"] if a_is_low else agg["low_wins"]
    games = agg["games"]
    a_margin_total = agg["low_margin_total"] if a_is_low else -agg["low_margin_total"]

    def meeting_scores(meeting: dict[str, Any]) -> tuple[float, float]:
        if a_is_low:
            return meeting["low_score"], meeting["high_score"]
        return meeting["high_score"], meeting["low_score"]

    highest = max(agg["meetings"], key=lambda mt: mt["low_score"] + mt["high_score"])
    lopsided = max(agg["meetings"], key=lambda mt: abs(mt["low_margin"]))
    closest = min(agg["meetings"], key=lambda mt: abs(mt["low_margin"]))
    h_a, h_b = meeting_scores(highest)
    l_margin = lopsided["low_margin"] if a_is_low else -lopsided["low_margin"]
    c_margin = closest["low_margin"] if a_is_low else -closest["low_margin"]

    # Every meeting, chronological, oriented to A — drives the rivalry margin line.
    meetings_for_a: list[dict[str, Any]] = []
    for mt in sorted(agg["meetings"], key=lambda x: (x["season_year"] or 0, x["week"] or 0)):
        a_score, b_score = meeting_scores(mt)
        m_for_a = mt["low_margin"] if a_is_low else -mt["low_margin"]
        meetings_for_a.append(
            {
                "season_year": mt["season_year"],
                "week": mt["week"],
                "matchup_id": mt["matchup_id"],
                "margin_for_a": round(m_for_a, 2),
                "a_score": a_score,
                "b_score": b_score,
                "is_playoff": mt["is_true_playoff"],
                "is_championship": mt["is_championship"],
            }
        )

    return {
        **base,
        "available": True,
        "games_played": games,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": agg["ties"],
        "a_win_pct": round((a_wins + 0.5 * agg["ties"]) / games, 4),
        "avg_margin_for_a": round(a_margin_total / games, 2),
        # Signed running total across every meeting (distinct from the per-game
        # average); positive means A is up on aggregate points.
        "cumulative_margin_for_a": round(a_margin_total, 2),
        "playoff_meetings": agg["playoff_meetings"],
        "highest_scoring_meeting": {
            "season_year": highest["season_year"],
            "week": highest["week"],
            "matchup_id": highest["matchup_id"],
            "a_score": h_a,
            "b_score": h_b,
        },
        "most_lopsided_meeting": {
            "season_year": lopsided["season_year"],
            "week": lopsided["week"],
            "matchup_id": lopsided["matchup_id"],
            "margin_for_a": round(l_margin, 2),
        },
        "closest_meeting": {
            "season_year": closest["season_year"],
            "week": closest["week"],
            "matchup_id": closest["matchup_id"],
            "margin_for_a": round(c_margin, 2),
        },
        "meetings": meetings_for_a,
    }


def rivalry_matrix(session: Session) -> dict[str, Any]:
    """Full NxN win-pct matrix (row owner's wins / games vs column owner)."""
    names = owner_name_map(session)
    active = owner_active_map(session)
    owner_ids = sorted(names)
    pairs = all_pairwise(session)

    cells: list[dict[str, Any]] = []
    for a in owner_ids:
        for b in owner_ids:
            if a == b:
                cells.append({"a": a, "b": b, "games": 0, "a_win_pct": None})
                continue
            low, high = (a, b) if a < b else (b, a)
            agg = pairs.get((low, high))
            if agg is None or agg["games"] == 0:
                cells.append({"a": a, "b": b, "games": 0, "a_win_pct": None})
                continue
            a_wins = agg["low_wins"] if a == low else agg["high_wins"]
            cells.append(
                {
                    "a": a,
                    "b": b,
                    "games": agg["games"],
                    "a_win_pct": round((a_wins + 0.5 * agg["ties"]) / agg["games"], 4),
                }
            )

    return {
        "owners": [
            {
                "owner_id": oid,
                "display_name": names.get(oid),
                "is_active": active.get(oid, True),
            }
            for oid in owner_ids
        ],
        "cells": cells,
    }


def closest_rivalry(session: Session) -> dict[str, Any] | None:
    """The genuinely dead-even rivalry: the pair whose all-time win pct is nearest
    0.5, gated by a real sample (``MIN_DEAD_EVEN_GAMES``).

    Balance is the primary key — a lopsided 21-9 series is not "even" however many
    times it was played — with more games as the tiebreak between equally balanced
    pairs. Crowned among **qualified** pairs (both owners still active or a
    significant-stint departure) so the headline is a current, compelling rivalry,
    falling back to all pairs only if none qualify. A records-book stat."""
    names = owner_name_map(session)
    prominence = owner_prominence_map(session)
    pairs = all_pairwise(session)

    def pick(qualified_only: bool) -> Pair | None:
        best: tuple[float, int, Pair] | None = None
        for key, agg in pairs.items():
            if agg["games"] < MIN_DEAD_EVEN_GAMES:
                continue
            if qualified_only and min(prominence.get(o, 0) for o in key) < 1:
                continue
            low_pct = (agg["low_wins"] + 0.5 * agg["ties"]) / agg["games"]
            closeness = abs(low_pct - 0.5)
            # Closest to even first, then more games, then a stable id tiebreak.
            candidate = (closeness, -agg["games"], key)
            if best is None or candidate < best:
                best = candidate
        return best[2] if best is not None else None

    chosen = pick(qualified_only=True) or pick(qualified_only=False)
    if chosen is None:
        return None
    low, high = chosen
    agg = pairs[chosen]
    return {
        "owner_a": {"owner_id": low, "display_name": names.get(low)},
        "owner_b": {"owner_id": high, "display_name": names.get(high)},
        "games_played": agg["games"],
        "a_wins": agg["low_wins"],
        "b_wins": agg["high_wins"],
        "ties": agg["ties"],
    }
