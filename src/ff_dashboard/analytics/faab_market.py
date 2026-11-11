"""The season's FAAB market (Sleeper D6): spend, the biggest bids, and bid wars.

A **bid war** is every ``waiver_add`` claim on one player in one week, when at least one claim
lost (``status='failed'``, Sleeper only). The winner is the claim that went through; ``margin`` is
the winning bid minus the best losing bid. A $0 bid is a real bid. A lost claim with no rival (for
example, not enough budget) is a failed bid but not a war.

Legacy (NFL.com) seasons record winning bids only, so their failed bids are a capability gap
(``faab_failed_bids`` = ``not_on_platform``), never an empty war list presented as "no wars".
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

from ff_pipeline.repository.models import Player, Team, Transaction
from ff_pipeline.repository.queries import get_season, get_team
from sqlalchemy import select

from ff_dashboard.analytics.aggregation import is_failed_claim, pct_of_budget
from ff_dashboard.analytics.common import owner_name_map
from ff_dashboard.analytics.historical_team_names import period_team_name
from ff_dashboard.analytics.platform import AVAILABLE, season_capabilities

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Season
    from sqlalchemy.orm import Session

FAAB_BASE_BUDGET = 100.0
TOP_BIDS = 10
FAILED_BIDS_KEY = "faab_failed_bids"


def faab_bid(extra_data: dict[str, Any] | None) -> float | None:
    """The claim's FAAB bid; ``0`` is a real (free) bid, ``None`` means none was recorded."""
    extra = extra_data or {}
    for key in ("faab_bid", "faab", "bid"):  # key presence, not truthiness: $0 is a real bid
        raw = extra.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def season_budget(season: Season) -> float:
    """The season's per-team FAAB budget: the platform setting, else the legacy $100 base."""
    settings = (season.settings_snapshot or {}).get("settings") or {}
    budget = settings.get("waiver_budget")
    return float(budget) if isinstance(budget, (int, float)) and budget > 0 else FAAB_BASE_BUDGET


def _tid(txn: Transaction) -> int:
    """A claim's team (always set on a ``waiver_add``)."""
    return cast("int", txn.team_id)


def _bid_order(b: dict[str, Any]) -> tuple[bool, float]:
    """Winning claim first, then by bid, highest first (a missing bid last)."""
    bid = b["bid"]
    return (not b["won"], -(bid if isinstance(bid, (int, float)) else -1.0))


def _claims(session: Session, season_id: int) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction)
            .where(Transaction.season_id == season_id, Transaction.transaction_type == "waiver_add")
            .order_by(Transaction.effective_week, Transaction.transaction_id)
        )
    )


class _Refs:
    """Team / player refs, resolved once per call."""

    def __init__(self, session: Session, season: Season) -> None:
        self.session, self.season = session, season
        self.owners = owner_name_map(session)
        self._teams: dict[int, dict[str, Any]] = {}
        self._players: dict[int, dict[str, Any]] = {}

    def team(self, team_id: int | None) -> dict[str, Any] | None:
        if team_id is None:
            return None
        if team_id not in self._teams:
            t = get_team(self.session, team_id)
            self._teams[team_id] = {
                "team_id": team_id,
                "team_name": period_team_name(t, self.season.year) if t is not None else None,
                "owner_id": t.owner_id if t is not None else None,
                "owner_name": self.owners.get(t.owner_id) if t is not None else None,
            }
        return self._teams[team_id]

    def player(self, player_id: int | None) -> dict[str, Any] | None:
        if player_id is None:
            return None
        if player_id not in self._players:
            p = self.session.get(Player, player_id)
            self._players[player_id] = {
                "player_id": player_id,
                "player_name": p.name_full if p is not None else None,
                "position": p.position if p is not None else None,
            }
        return self._players[player_id]


def _bid_wars(claims: list[Transaction], refs: _Refs) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for c in claims:
        if c.player_id is not None and c.effective_week is not None:
            groups[(int(c.effective_week), int(c.player_id))].append(c)
    wars: list[dict[str, Any]] = []
    for (week, player_id), group in groups.items():
        lost = [c for c in group if is_failed_claim(c)]
        if not lost or len(group) < 2:
            continue
        won = [c for c in group if not is_failed_claim(c)]
        winner = won[0] if won else None
        winning_bid = faab_bid(winner.extra_data) if winner is not None else None
        losing = [b for b in (faab_bid(c.extra_data) for c in lost) if b is not None]
        bids = sorted(
            (
                {
                    "team": refs.team(_tid(c)),
                    "bid": faab_bid(c.extra_data),
                    "won": not is_failed_claim(c),
                    "failure_reason": (c.extra_data or {}).get("failure_reason"),
                }
                for c in group
            ),
            key=_bid_order,
        )
        wars.append(
            {
                "week": week,
                "player": refs.player(player_id),
                "winner": refs.team(_tid(winner)) if winner is not None else None,
                "winning_bid": winning_bid,
                "margin": round(winning_bid - max(losing), 2)
                if winning_bid is not None and losing
                else None,
                "bids": bids,
            }
        )
    wars.sort(key=lambda w: (w["week"], -(w["winning_bid"] or 0.0)))
    return wars


def season_faab_market(session: Session, season_id: int) -> dict[str, Any] | None:
    """Spend per team, the biggest winning bids and the bid wars of one season; ``None`` if absent."""
    season = get_season(session, season_id)
    if season is None:
        return None
    capability = season_capabilities(session, season_id).get(FAILED_BIDS_KEY)
    failed_available = (capability or {}).get("state") == AVAILABLE
    claims = _claims(session, season_id)
    base: dict[str, Any] = {
        "season_id": season_id,
        "season_year": season.year,
        "failed_bids_capability": capability,
    }
    winning = [c for c in claims if not is_failed_claim(c) and faab_bid(c.extra_data) is not None]
    if not winning and not any(faab_bid(c.extra_data) is not None for c in claims):
        return {
            **base,
            "is_faab_era": False,
            "budget": None,
            "teams": [],
            "top_bids": [],
            "bid_wars": [],
        }

    budget = season_budget(season)
    refs = _Refs(session, season)
    spent: dict[int, float] = defaultdict(float)
    wins: dict[int, int] = defaultdict(int)
    largest: dict[int, float] = {}
    for c in winning:
        tid, bid = _tid(c), faab_bid(c.extra_data) or 0.0
        spent[tid] += bid
        wins[tid] += 1
        largest[tid] = max(largest.get(tid, 0.0), bid)
    losses: dict[int, int] = defaultdict(int)
    for c in claims:
        if is_failed_claim(c):
            losses[_tid(c)] += 1

    team_ids = [
        int(t) for t in session.scalars(select(Team.team_id).where(Team.season_id == season_id))
    ]
    teams: list[dict[str, Any]] = [
        {
            "team": refs.team(tid),
            "spent": round(spent.get(tid, 0.0), 2),
            "pct_of_budget": pct_of_budget(spent.get(tid, 0.0), budget),
            "winning_bids": wins.get(tid, 0),
            # Lost bids are only known where the platform records them; else a gap, never 0.
            "failed_bids": losses.get(tid, 0) if failed_available else None,
            "largest_bid": largest.get(tid),
        }
        for tid in team_ids
    ]
    teams.sort(key=lambda r: (-float(r["spent"]), int(r["team"]["team_id"])))
    top = sorted(winning, key=lambda c: (-(faab_bid(c.extra_data) or 0.0), c.transaction_id))[
        :TOP_BIDS
    ]
    return {
        **base,
        "is_faab_era": True,
        "budget": budget,
        "teams": teams,
        "top_bids": [
            {
                "week": c.effective_week,
                "team": refs.team(_tid(c)),
                "player": refs.player(c.player_id),
                "bid": faab_bid(c.extra_data),
            }
            for c in top
        ],
        "bid_wars": _bid_wars(claims, refs) if failed_available else [],
    }


def team_failed_bids(session: Session, team_id: int) -> list[dict[str, Any]]:
    """This team's lost claims, each with the winning claim when someone else got the player."""
    team = get_team(session, team_id)
    season = get_season(session, team.season_id) if team is not None else None
    if team is None or season is None:
        return []
    claims = _claims(session, season.season_id)
    refs = _Refs(session, season)
    winners = {
        (int(c.effective_week), int(c.player_id)): c
        for c in claims
        if not is_failed_claim(c) and c.effective_week is not None and c.player_id is not None
    }
    out: list[dict[str, Any]] = []
    for c in claims:
        if _tid(c) != team_id or not is_failed_claim(c):
            continue
        w = winners.get((int(c.effective_week or 0), int(c.player_id or 0)))
        out.append(
            {
                "week": c.effective_week,
                "player": refs.player(c.player_id),
                "bid": faab_bid(c.extra_data),
                "failure_reason": (c.extra_data or {}).get("failure_reason"),
                "winner": refs.team(_tid(w)) if w is not None else None,
                "winning_bid": faab_bid(w.extra_data) if w is not None else None,
            }
        )
    return out
