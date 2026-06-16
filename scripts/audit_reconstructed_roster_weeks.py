#!/usr/bin/env python3
"""Read-only audit for reconstructed (all-``audit``) roster weeks.

A ``team_rosters`` week whose only ``snapshot_kind`` is ``audit`` is a
non-authoritative live capture stamped onto a week slot, never superseded by an
authoritative ``history``/``draft``/``pre_kickoff`` snapshot — so its per-player
roster→team attribution and slots are approximate (see
``analytics/roster_snapshots``). This lists every such ``(season, week, team)``
cell and flags the ones that back an actual fantasy matchup (i.e. user-visible
box scores / team pages). Run it after each ingest to catch the class early.

Local verification helper, not a CI test (it reads the live DB).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any

from ff_pipeline.repository.models import Matchup, Season, TeamRoster
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from ff_dashboard.analytics.roster_snapshots import is_reconstructed_week, snapshot_kind
from ff_dashboard.engine import create_readonly_engine
from ff_dashboard.settings import get_settings


def audit(session: Session) -> dict[str, Any]:
    backs_a_matchup = exists().where(
        Matchup.team_id == TeamRoster.team_id,
        Matchup.week == TeamRoster.week,
        Matchup.season_id == Season.season_id,
    )
    rows = session.execute(
        select(TeamRoster, backs_a_matchup)
        .join(Season, Season.year == TeamRoster.season_year)
        .where(TeamRoster.week > 0)
    ).all()

    # Group snapshot kinds per (season, week, team), tracking matchup visibility.
    kinds: defaultdict[tuple[int, int, int], list[str | None]] = defaultdict(list)
    visible: dict[tuple[int, int, int], bool] = {}
    for roster, backs in rows:
        cell = (int(roster.season_year), int(roster.week), int(roster.team_id))
        kinds[cell].append(snapshot_kind(roster))
        visible[cell] = visible.get(cell, False) or bool(backs)

    reconstructed = [cell for cell, ks in kinds.items() if is_reconstructed_week(ks)]
    reconstructed.sort()
    visible_cells = [c for c in reconstructed if visible[c]]

    def fmt(cells: list[tuple[int, int, int]]) -> list[dict[str, int]]:
        return [{"season_year": s, "week": w, "team_id": t} for s, w, t in cells]

    # Roll up to (season, week) so the headline reads "2025 W1: 12", not 12 rows.
    by_week: defaultdict[tuple[int, int], int] = defaultdict(int)
    for s, w, _ in reconstructed:
        by_week[(s, w)] += 1

    return {
        "scope": "team_rosters cells (season, week, team) with week > 0",
        "reconstructed_cells": len(reconstructed),
        "reconstructed_by_week": {f"{s} W{w}": n for (s, w), n in sorted(by_week.items())},
        "matchup_visible_cells": len(visible_cells),
        "matchup_visible": fmt(visible_cells),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=get_settings().resolved_database_url())
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit non-zero if any reconstructed week backs a real matchup "
            "(user-visible). Use as a periodic real-DB guard after ingests."
        ),
    )
    args = parser.parse_args()

    engine = create_readonly_engine(args.database_url)
    with Session(engine) as session:
        result = audit(session)
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.strict and result["matchup_visible_cells"]:
        print(
            f"STRICT: {result['matchup_visible_cells']} reconstructed cell(s) back a "
            "live matchup — re-ingest those weeks via the history crawler.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
