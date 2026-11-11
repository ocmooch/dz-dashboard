"""The traded future-pick ledger (Sleeper D6): who owns which future draft pick.

Upstream keys ``traded_picks`` by owner (stable across seasons), so each row names the original
owner, the current owner and the previous one. Only picks that changed hands are recorded; an
untraded pick stays with its original owner and isn't listed.

``traded_future_picks`` is an activity capability: on Sleeper an empty ledger is a real answer
("no picks traded yet"). Where no played season has it (NFL.com only), the ledger is a gap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries

from ff_dashboard.analytics.aggregation import seasons_with
from ff_dashboard.analytics.common import owner_name_map, require_league

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

CAPABILITY = "traded_future_picks"


def _owner(owners: dict[int, str | None], owner_id: int | None) -> dict[str, Any] | None:
    if owner_id is None:
        return None
    return {"owner_id": owner_id, "owner_name": owners.get(owner_id)}


def _pick_order(p: dict[str, Any]) -> tuple[int, int, int]:
    original = p["original_owner"] or {}
    return (int(p["pick_season"]), int(p["round"]), int(original.get("owner_id") or 0))


def league_pick_ledger(session: Session) -> dict[str, Any]:
    """``{available, reason, picks[]}``: every traded future pick and its current owner."""
    league = require_league(session)
    if not seasons_with(session, CAPABILITY):
        return {"available": False, "reason": CAPABILITY, "picks": []}
    owners = owner_name_map(session)
    rows = queries.traded_picks_for_league(session, league.league_id)
    picks = [
        {
            "pick_season": r.pick_season,
            "round": r.round,
            "original_owner": _owner(owners, r.original_owner_id),
            "current_owner": _owner(owners, r.current_owner_id),
            "previous_owner": _owner(owners, r.previous_owner_id),
        }
        for r in rows
    ]
    picks.sort(key=_pick_order)
    return {"available": True, "reason": None, "picks": picks}
