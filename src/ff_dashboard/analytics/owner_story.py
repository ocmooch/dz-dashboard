"""Per-owner "Your Story" superlatives — the manager-profile highlight reel.

This is the personal analogue of :mod:`analytics.rivalries`: where that module
ranks the whole league's pairings, this one reduces **one owner's** history into a
small set of voiced superlatives. It reuses the exact sources the rivalries bundle
trusts so the two can never disagree:

* :func:`head_to_head.all_pairwise` — every owner-vs-owner meeting, already deduped
  to one row per game and bye-free, for the signature win / heartbreak / nemesis /
  favourite victim / high-water mark.
* :func:`standings.standings_insights` — per-season schedule luck (all-play
  expected wins), for the luckiest / unluckiest season.

The honesty rules from the project's hard rules are non-negotiable here:

* **Every superlative gates on a min-sample bar and is simply absent when it does
  not clear it** — the field comes back ``None``, never a forced 0 or a fake value.
* Single-game superlatives (signature win, heartbreak, high-water mark) require the
  game to actually exist (≥1 win for the signature win, ≥1 loss for the heartbreak).
* Nemesis / favourite victim reuse the rivalries ``MIN_NEMESIS_GAMES`` gate.
* Luck superlatives are **sign-gated**: a "luckiest" season is only shown when the
  owner actually banked schedule luck (max ``luck_delta`` > 0), and "unluckiest"
  only when the schedule genuinely cost them (min ``luck_delta`` < 0). An owner
  whose best season was merely break-even gets no luck line rather than a misleading
  "luckiest" label.
* Every concrete game carries a ``matchup_id`` for deep-linking and an opponent
  ``OwnerRef`` for linking to the pairwise / profile pages.

The per-manager **epithet** (:func:`assign_epithet`) lives here too but is a
*separate, reviewable proposal* — it is deliberately NOT part of :func:`owner_story`
or the shipped endpoint. See ``docs/plans/owner-epithet-proposal.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.queries import get_owner

from ff_dashboard.analytics.common import owner_name_map
from ff_dashboard.analytics.head_to_head import all_pairwise
from ff_dashboard.analytics.owners import owner_seasons
from ff_dashboard.analytics.rivalries import MIN_NEMESIS_GAMES
from ff_dashboard.analytics.standings import standings_insights

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Reuse the rivalries nemesis bar so the "Kryptonite" / "Favourite victim" lines on
# a profile agree with the league-wide Nemesis & Favourite Victim band.
MIN_RIVAL_GAMES = MIN_NEMESIS_GAMES


def _ref(owner_id: int, names: dict[int, str | None]) -> dict[str, Any]:
    return {"owner_id": owner_id, "display_name": names.get(owner_id)}


@dataclass(frozen=True)
class _OwnerMeeting:
    """One meeting from this owner's point of view (margin is the owner's)."""

    opponent: int
    owner_score: float
    opp_score: float
    margin: float  # owner_score - opp_score
    season_year: int | None
    week: int | None
    matchup_id: int | None
    is_playoff: bool


def _owner_meetings(session: Session, owner_id: int) -> list[_OwnerMeeting]:
    """Every scored meeting this owner played, oriented to them."""
    out: list[_OwnerMeeting] = []
    for (low, high), agg in all_pairwise(session).items():
        if owner_id not in (low, high):
            continue
        is_low = owner_id == low
        opponent = high if is_low else low
        for mt in agg["meetings"]:
            if is_low:
                owner_score, opp_score, margin = mt["low_score"], mt["high_score"], mt["low_margin"]
            else:
                owner_score, opp_score, margin = (
                    mt["high_score"],
                    mt["low_score"],
                    -mt["low_margin"],
                )
            out.append(
                _OwnerMeeting(
                    opponent=opponent,
                    owner_score=owner_score,
                    opp_score=opp_score,
                    margin=margin,
                    season_year=mt["season_year"],
                    week=mt["week"],
                    matchup_id=mt["matchup_id"],
                    is_playoff=mt["is_playoff"],
                )
            )
    return out


def _meeting_item(m: _OwnerMeeting, names: dict[int, str | None]) -> dict[str, Any]:
    return {
        "opponent": _ref(m.opponent, names),
        "owner_score": round(m.owner_score, 2),
        "opponent_score": round(m.opp_score, 2),
        "margin": round(abs(m.margin), 2),
        "season_year": m.season_year,
        "week": m.week,
        "matchup_id": m.matchup_id,
        "is_playoff": m.is_playoff,
    }


def _signature_win(
    meetings: list[_OwnerMeeting], names: dict[int, str | None]
) -> dict[str, Any] | None:
    """Biggest beating this owner ever handed out (max winning margin)."""
    wins = [m for m in meetings if m.margin > 0]
    if not wins:
        return None
    best = max(wins, key=lambda m: m.margin)
    return _meeting_item(best, names)


def _heartbreak(
    meetings: list[_OwnerMeeting], names: dict[int, str | None]
) -> dict[str, Any] | None:
    """Closest loss — preferring a playoff loss when one exists (a true elimination
    heartbreak), else the narrowest regular-season loss."""
    losses = [m for m in meetings if m.margin < 0]
    if not losses:
        return None
    playoff_losses = [m for m in losses if m.is_playoff]
    pool = playoff_losses or losses
    closest = min(pool, key=lambda m: abs(m.margin))
    return _meeting_item(closest, names)


def _high_water_mark(
    meetings: list[_OwnerMeeting], names: dict[int, str | None]
) -> dict[str, Any] | None:
    """Single highest score this owner ever posted in a game."""
    if not meetings:
        return None
    best = max(meetings, key=lambda m: m.owner_score)
    return {
        "opponent": _ref(best.opponent, names),
        "score": round(best.owner_score, 2),
        "opponent_score": round(best.opp_score, 2),
        "season_year": best.season_year,
        "week": best.week,
        "matchup_id": best.matchup_id,
    }


def _opp_record_item(opp: int, rec: dict[str, Any], names: dict[int, str | None]) -> dict[str, Any]:
    return {
        "opponent": _ref(opp, names),
        "games": rec["games"],
        "wins": rec["wins"],
        "losses": rec["losses"],
        "ties": rec["ties"],
        "win_pct": round(rec["win_pct"], 4),
    }


def _nemesis_and_victim(
    meetings: list[_OwnerMeeting], names: dict[int, str | None]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Worst-record (nemesis) and best-record (favourite victim) opponents.

    Min-sample gated on :data:`MIN_RIVAL_GAMES`. When a single opponent qualifies
    the two collide, so only the side the record supports is kept (mirrors
    :func:`rivalries.manager_nemeses`).
    """
    by_opp: dict[int, dict[str, Any]] = {}
    for m in meetings:
        rec = by_opp.setdefault(m.opponent, {"games": 0, "wins": 0, "losses": 0, "ties": 0})
        rec["games"] += 1
        if m.margin > 0:
            rec["wins"] += 1
        elif m.margin < 0:
            rec["losses"] += 1
        else:
            rec["ties"] += 1
    for rec in by_opp.values():
        rec["win_pct"] = (rec["wins"] + 0.5 * rec["ties"]) / rec["games"]

    qualifying = {opp: rec for opp, rec in by_opp.items() if rec["games"] >= MIN_RIVAL_GAMES}
    if not qualifying:
        return None, None

    nem_opp = min(qualifying, key=lambda o: (qualifying[o]["win_pct"], -qualifying[o]["games"]))
    vic_opp = max(qualifying, key=lambda o: (qualifying[o]["win_pct"], qualifying[o]["games"]))
    nemesis: dict[str, Any] | None = _opp_record_item(nem_opp, qualifying[nem_opp], names)
    victim: dict[str, Any] | None = _opp_record_item(vic_opp, qualifying[vic_opp], names)
    if nem_opp == vic_opp:
        if qualifying[nem_opp]["win_pct"] <= 0.5:
            victim = None
        else:
            nemesis = None
    return nemesis, victim


def _luck_extremes(
    session: Session, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Luckiest / unluckiest season by all-play ``luck_delta`` (sign-gated).

    Walks only this owner's seasons. "Luckiest" is shown only when the best season
    actually banked luck (delta > 0); "unluckiest" only when a season truly cost
    them (delta < 0). A break-even owner gets neither — never a misleading label.
    """
    per_season: list[dict[str, Any]] = []
    for r in rows:
        insight = standings_insights(session, r["season_id"])
        if insight is None or not insight.get("available"):
            continue
        team = next((t for t in insight["teams"] if t["team_id"] == r["team_id"]), None)
        if team is None:
            continue
        per_season.append(
            {
                "season_year": r["season_year"],
                "luck_delta": team["luck_delta"],
                "actual_wins": team["actual_wins"],
                "expected_wins": team["expected_wins"],
            }
        )
    if not per_season:
        return None, None

    best = max(per_season, key=lambda s: s["luck_delta"])
    worst = min(per_season, key=lambda s: s["luck_delta"])
    luckiest = best if best["luck_delta"] > 0 else None
    unluckiest = worst if worst["luck_delta"] < 0 else None
    return luckiest, unluckiest


def owner_story(session: Session, owner_id: int) -> dict[str, Any] | None:
    """The "Your Story" bundle for one owner (``None`` if the owner doesn't exist).

    Each superlative is either a rich, deep-linkable object or ``None`` when it does
    not clear its bar. ``available`` is True iff at least one superlative is present.
    """
    if get_owner(session, owner_id) is None:
        return None
    names = owner_name_map(session)
    meetings = _owner_meetings(session, owner_id)
    rows = owner_seasons(session, owner_id) or []

    nemesis, victim = _nemesis_and_victim(meetings, names)
    luckiest, unluckiest = _luck_extremes(session, rows)

    fields: dict[str, Any] = {
        "signature_win": _signature_win(meetings, names),
        "heartbreak": _heartbreak(meetings, names),
        "high_water_mark": _high_water_mark(meetings, names),
        "nemesis": nemesis,
        "favorite_victim": victim,
        "luckiest_season": luckiest,
        "unluckiest_season": unluckiest,
    }
    return {
        "owner": _ref(owner_id, names),
        "available": any(v is not None for v in fields.values()),
        **fields,
    }


# ---------------------------------------------------------------------------
# Per-manager epithet — SEPARATE, REVIEWABLE PROPOSAL. Not wired into
# owner_story() or the /story endpoint; ships only after product-owner sign-off
# on the vocabulary. Thresholds are documented in docs/plans/owner-epithet-proposal.md
# and tested in tests/test_owner_story.py.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OwnerFingerprint:
    """The statistical inputs an epithet is assigned from."""

    seasons_played: int
    championships: int
    runner_ups: int
    best_finish: int | None
    win_pct: float | None
    best_luck_delta: float | None  # max single-season luck_delta
    worst_luck_delta: float | None  # min single-season luck_delta


# Min tenure before any epithet is even considered — a one-season manager has no
# "story" yet, so they simply get none.
MIN_EPITHET_SEASONS = 3
# Archetype thresholds (documented; tuned for full-season real-DB history).
EPITHET_DYNASTY_TITLES = 3  # "The Dynasty"
EPITHET_BRIDESMAID_RUNNERUPS = 2  # "The Bridesmaid" (and never a title)
EPITHET_LUCKY_DELTA = 2.0  # "The Lucky Devil" — a season the schedule gave ≥2 wins
EPITHET_ROBBED_DELTA = -2.0  # "The Snakebitten" — a season that cost ≥2 wins
EPITHET_CONTENDER_WINPCT = 0.60  # "The Powerhouse" — sustained dominance, no title


def assign_epithet(fp: OwnerFingerprint) -> dict[str, Any] | None:
    """Assign at most one affectionate archetype, or ``None`` when nothing clears
    its bar. Priority order is fixed; the first archetype whose threshold is met
    wins. A small, celebratory/wry vocabulary — never cruel about a real person.

    The bars are deliberately strict: an owner who doesn't clearly fit an archetype
    gets **no** epithet rather than a forced or generic one.
    """
    if fp.seasons_played < MIN_EPITHET_SEASONS:
        return None

    if fp.championships >= EPITHET_DYNASTY_TITLES:
        return {
            "label": "The Dynasty",
            "blurb": f"{fp.championships} titles — the standard everyone else is measured against.",
        }
    if fp.championships == 0 and fp.runner_ups >= EPITHET_BRIDESMAID_RUNNERUPS:
        return {
            "label": "The Bridesmaid",
            "blurb": f"{fp.runner_ups} times to the final, never the ring.",
        }
    if fp.championships == 0 and fp.win_pct is not None and fp.win_pct >= EPITHET_CONTENDER_WINPCT:
        return {
            "label": "The Powerhouse",
            "blurb": "A perennial contender still chasing that first title.",
        }
    if fp.best_luck_delta is not None and fp.best_luck_delta >= EPITHET_LUCKY_DELTA:
        return {
            "label": "The Lucky Devil",
            "blurb": "The schedule has been a very good friend.",
        }
    if fp.worst_luck_delta is not None and fp.worst_luck_delta <= EPITHET_ROBBED_DELTA:
        return {
            "label": "The Snakebitten",
            "blurb": "Has the all-play wins to show for it; the schedule disagreed.",
        }
    return None
