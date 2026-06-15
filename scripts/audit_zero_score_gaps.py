#!/usr/bin/env python3
"""Read-only audit for weekly player score zero/gap semantics.

This is intentionally a local verification helper, not a CI test. It scans only
roster rows attached to actual fantasy matchup team/weeks and classifies each
row the same way the dashboard's week-scoped surfaces do.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any

from ff_pipeline.repository.models import Matchup, Player, PlayerStatsScored, Season, TeamRoster
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from ff_dashboard.analytics.coverage import seasons_scored
from ff_dashboard.analytics.matchups import DEF_SLOTS, _authoritative_points, classify_zero
from ff_dashboard.engine import create_readonly_engine
from ff_dashboard.settings import get_settings


def _example(
    *,
    season_year: int,
    week: int,
    team_id: int,
    player_id: int,
    player_name: str | None,
    slot: str | None,
    points: float | None,
    nflverse_points: float | None,
    opponent: str | None,
) -> dict[str, Any]:
    return {
        "season_year": season_year,
        "week": week,
        "team_id": team_id,
        "player_id": player_id,
        "player_name": player_name,
        "slot": slot,
        "points": points,
        "nflverse_points": nflverse_points,
        "opponent": opponent,
    }


def audit(session: Session, *, example_limit: int = 5) -> dict[str, Any]:
    scored_years = set(seasons_scored(session))
    actual_week = exists().where(
        Matchup.team_id == TeamRoster.team_id,
        Matchup.week == TeamRoster.week,
        Matchup.season_id == Season.season_id,
    )
    roster_rows = session.execute(
        select(TeamRoster, Player, Season.season_id, Season.year)
        .join(Player, Player.player_id == TeamRoster.player_id)
        .join(Season, Season.year == TeamRoster.season_year)
        .where(TeamRoster.week > 0, actual_week)
        .order_by(Season.year, TeamRoster.week, TeamRoster.team_id, Player.name_full)
    ).all()

    player_ids = sorted({int(roster.player_id) for roster, _, _, _ in roster_rows})
    season_ids = sorted({int(season_id) for _, _, season_id, _ in roster_rows})
    weeks = sorted({int(roster.week) for roster, _, _, _ in roster_rows})
    scored_rows = session.execute(
        select(
            PlayerStatsScored.season_id,
            PlayerStatsScored.week,
            PlayerStatsScored.player_id,
            PlayerStatsScored.total_points,
        ).where(
            PlayerStatsScored.season_id.in_(season_ids),
            PlayerStatsScored.week.in_(weeks),
            PlayerStatsScored.player_id.in_(player_ids),
        )
    ).all()
    scored = {
        (int(season_id), int(week), int(player_id)): float(points)
        for season_id, week, player_id, points in scored_rows
        if points is not None
    }

    counts: defaultdict[str, int] = defaultdict(int)
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(category: str, item: dict[str, Any]) -> None:
        counts[category] += 1
        if len(examples[category]) < example_limit:
            examples[category].append(item)

    for roster, player, season_id, season_year in roster_rows:
        season_year = int(season_year)
        key = (int(season_id), int(roster.week), int(roster.player_id))
        nflverse_points = scored.get(key)
        authoritative = _authoritative_points(roster)
        points = authoritative if authoritative is not None else nflverse_points
        extra = roster.extra_data if isinstance(roster.extra_data, dict) else {}
        raw_opponent = extra.get("opponent")
        opponent = raw_opponent if isinstance(raw_opponent, str) else None
        item = _example(
            season_year=season_year,
            week=int(roster.week),
            team_id=int(roster.team_id),
            player_id=int(roster.player_id),
            player_name=player.name_full,
            slot=roster.roster_slot,
            points=round(points, 2) if points is not None else None,
            nflverse_points=round(nflverse_points, 2) if nflverse_points is not None else None,
            opponent=opponent,
        )

        if season_year not in scored_years:
            add("unscored_season_rows", item)
            continue
        if points is None and roster.roster_slot in DEF_SLOTS:
            add("missing_dst", item)
            continue
        if points is None:
            points = 0.0
            item["points"] = 0.0

        if points != 0.0:
            add("non_zero_scored", item)
            continue

        zero_reason, _ = classify_zero(points, opponent, nflverse_points)
        if zero_reason == "bye":
            add("bye_zero", item)
        elif zero_reason == "did_not_play":
            add("did_not_play_missing_row", item)
        elif zero_reason == "unexpected":
            add("unexpected_zero", item)
        else:
            add("true_zero_with_raw_stat_row", item)

    return {
        "scope": "team_rosters rows for actual fantasy matchup team/weeks",
        "total_rows": len(roster_rows),
        "counts": dict(sorted(counts.items())),
        "examples": dict(sorted(examples.items())),
    }


# On the real DB these categories must be empty: an authoritative-0 row that
# nflverse credits material points for is drift to investigate upstream, and a
# missing D/ST row is a reconstruction hole that must stay a gap, never a zero.
_STRICT_CATEGORIES = ("unexpected_zero", "missing_dst")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=get_settings().resolved_database_url())
    parser.add_argument("--examples", type=int, default=5)
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit non-zero if any unexpected-zero or missing-DST rows are found "
            "(for a periodic real-DB drift guard, not the fixture CI test)."
        ),
    )
    args = parser.parse_args()

    engine = create_readonly_engine(args.database_url)
    with Session(engine) as session:
        result = audit(session, example_limit=args.examples)
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.strict:
        offenders = {c: result["counts"].get(c, 0) for c in _STRICT_CATEGORIES}
        if any(offenders.values()):
            print(f"STRICT: drift detected — {offenders}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
