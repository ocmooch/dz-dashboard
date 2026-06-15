"""League-wide rivalry insights — reducers over the pairwise meeting history.

Everything here builds on :func:`head_to_head.all_pairwise`, which already dedupes
each game to one row and excludes byes, so this module never re-touches matchup
rows. It keys on **owners** and obeys the project's honesty rules:

* min-sample gates (a 1-0 pair is not a rivalry),
* missing data returns ``available: False`` / nulls, never zeros,
* every concrete game carries a ``matchup_id`` for deep-linking,
* no hardcoded years — the recency window is read from the data.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Season
from sqlalchemy import select

from ff_dashboard.analytics.bracket import season_bracket
from ff_dashboard.analytics.common import owner_active_map, owner_name_map
from ff_dashboard.analytics.head_to_head import all_pairwise, closest_rivalry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# --- min-sample gates (a record below these is not yet a rivalry) ------------
MIN_INTENSITY_GAMES = 4
MIN_NEMESIS_GAMES = 3
MIN_ACTIVE_STREAK = 3

# --- intensity tuning (documented knobs; tune against the real DB) -----------
_W_BALANCE = 0.30  # nearness to a 50/50 all-time split
_W_TIGHTNESS = 0.25  # close games (low average margin)
_W_RECENCY = 0.20  # met recently
_W_VOLUME = 0.15  # lots of meetings
_W_STAKES = 0.10  # postseason meetings
_VOL_CAP = 8  # games at which "volume" saturates
_MARGIN_CAP = 30.0  # avg margin at which "tightness" bottoms out
_RECENCY_HALFLIFE = 3.0  # seasons for the recency decay to halve
_STAKE_CAP = 3  # playoff meetings at which "stakes" saturates


def _ref(owner_id: int, names: dict[int, str | None]) -> dict[str, Any]:
    return {"owner_id": owner_id, "display_name": names.get(owner_id)}


def _winner_of(meeting: dict[str, Any], low: int, high: int) -> int | None:
    """The owner who won a meeting, or ``None`` on a tie (margin is low's view)."""
    lm = meeting["low_margin"]
    if lm > 0:
        return low
    if lm < 0:
        return high
    return None


def _meeting_item(
    meeting: dict[str, Any], low: int, high: int, names: dict[int, str | None]
) -> dict[str, Any]:
    """A single game oriented winner-first, with deep-link context."""
    lm = meeting["low_margin"]
    if lm >= 0:
        winner, loser = low, high
        w_score, l_score = meeting["low_score"], meeting["high_score"]
    else:
        winner, loser = high, low
        w_score, l_score = meeting["high_score"], meeting["low_score"]
    return {
        "winner": _ref(winner, names),
        "loser": _ref(loser, names),
        "winner_score": round(w_score, 2),
        "loser_score": round(l_score, 2),
        "margin": round(abs(lm), 2),
        "combined": round(meeting["low_score"] + meeting["high_score"], 2),
        "season_year": meeting["season_year"],
        "week": meeting["week"],
        "matchup_id": meeting["matchup_id"],
        "is_playoff": meeting["is_playoff"],
    }


def _pair_record_item(
    low: int, high: int, agg: dict[str, Any], names: dict[int, str | None]
) -> dict[str, Any]:
    return {
        "owner_a": _ref(low, names),
        "owner_b": _ref(high, names),
        "games": agg["games"],
        "a_wins": agg["low_wins"],
        "b_wins": agg["high_wins"],
        "ties": agg["ties"],
    }


def rivalry_records(session: Session) -> dict[str, Any]:
    """League-wide superlatives over every pairwise meeting."""
    names = owner_name_map(session)
    pairs = all_pairwise(session)

    flat: list[tuple[dict[str, Any], int, int]] = [
        (mt, low, high) for (low, high), agg in pairs.items() for mt in agg["meetings"]
    ]
    if not flat:
        return {"available": False, "reason": "no_meetings"}

    closest = min(flat, key=lambda t: abs(t[0]["low_margin"]))
    blowout = max(flat, key=lambda t: abs(t[0]["low_margin"]))
    shootout = max(flat, key=lambda t: t[0]["low_score"] + t[0]["high_score"])
    most_played = max(pairs.items(), key=lambda kv: kv[1]["games"])

    return {
        "available": True,
        "closest_game": _meeting_item(*closest, names),
        "biggest_blowout": _meeting_item(*blowout, names),
        "highest_scoring_duel": _meeting_item(*shootout, names),
        "most_played_pairing": _pair_record_item(
            most_played[0][0], most_played[0][1], most_played[1], names
        ),
        # closest_rivalry() is the existing "most games, nearest 50/50" stat.
        "dead_even_rivalry": closest_rivalry(session),
    }


def _streak_item(
    owner: int,
    opponent: int,
    length: int,
    start: dict[str, Any],
    end: dict[str, Any],
    names: dict[int, str | None],
    *,
    active: bool,
) -> dict[str, Any]:
    return {
        "owner": _ref(owner, names),
        "opponent": _ref(opponent, names),
        "length": length,
        "from_year": start["season_year"],
        "to_year": end["season_year"],
        "last_matchup_id": end["matchup_id"],
        "active": active,
    }


def rivalry_streaks(session: Session) -> dict[str, Any]:
    """Longest consecutive head-to-head win run, plus currently-active runs."""
    names = owner_name_map(session)
    pairs = all_pairwise(session)

    longest: dict[str, Any] | None = None
    active: list[dict[str, Any]] = []

    for (low, high), agg in pairs.items():
        order = sorted(agg["meetings"], key=lambda m: (m["season_year"] or 0, m["week"] or 0))
        cur_owner: int | None = None
        cur_len = 0
        cur_start: dict[str, Any] | None = None
        best: dict[str, Any] | None = None
        for mt in order:
            w = _winner_of(mt, low, high)
            if w is not None and w == cur_owner:
                cur_len += 1
            else:
                cur_owner = w
                cur_len = 1 if w is not None else 0
                cur_start = mt if w is not None else None
            if (
                cur_owner is not None
                and cur_start is not None
                and cur_len > (best["length"] if best else 0)
            ):
                best = {"owner": cur_owner, "start": cur_start, "end": mt, "length": cur_len}

        if best is not None:
            opp = high if best["owner"] == low else low
            item = _streak_item(
                best["owner"], opp, best["length"], best["start"], best["end"], names, active=False
            )
            if longest is None or item["length"] > longest["length"]:
                longest = item

        # The trailing run is "active" — it is the current state of the rivalry.
        if cur_owner is not None and cur_start is not None and cur_len >= MIN_ACTIVE_STREAK:
            opp = high if cur_owner == low else low
            active.append(
                _streak_item(cur_owner, opp, cur_len, cur_start, order[-1], names, active=True)
            )

    if longest is None:
        return {"available": False, "reason": "no_meetings"}
    active.sort(key=lambda s: (-s["length"], s["owner"]["owner_id"]))
    return {"available": True, "longest": longest, "active": active}


def rivalry_intensity(session: Session, top_n: int = 5) -> dict[str, Any]:
    """Composite "heat" leaderboard — which rivalries matter most right now."""
    names = owner_name_map(session)
    pairs = all_pairwise(session)
    latest_year = max(
        (
            mt["season_year"]
            for agg in pairs.values()
            for mt in agg["meetings"]
            if mt["season_year"] is not None
        ),
        default=None,
    )

    ranked: list[dict[str, Any]] = []
    for (low, high), agg in pairs.items():
        games = agg["games"]
        if games < MIN_INTENSITY_GAMES:
            continue
        low_pct = (agg["low_wins"] + 0.5 * agg["ties"]) / games
        balance = 1 - 2 * abs(low_pct - 0.5)
        avg_abs_margin = sum(abs(m["low_margin"]) for m in agg["meetings"]) / games
        tightness = 1 - min(avg_abs_margin / _MARGIN_CAP, 1)
        volume = min(games / _VOL_CAP, 1)
        last_year = max(
            (m["season_year"] for m in agg["meetings"] if m["season_year"] is not None),
            default=None,
        )
        if latest_year is not None and last_year is not None:
            recency = 0.5 ** ((latest_year - last_year) / _RECENCY_HALFLIFE)
        else:
            recency = 0.0
        stakes = min(agg["playoff_meetings"] / _STAKE_CAP, 1)
        heat = 100 * (
            _W_BALANCE * balance
            + _W_TIGHTNESS * tightness
            + _W_RECENCY * recency
            + _W_VOLUME * volume
            + _W_STAKES * stakes
        )
        last_meeting = max(agg["meetings"], key=lambda m: (m["season_year"] or 0, m["week"] or 0))
        ranked.append(
            {
                "owner_a": _ref(low, names),
                "owner_b": _ref(high, names),
                "heat": round(heat, 1),
                "games": games,
                "a_wins": agg["low_wins"],
                "b_wins": agg["high_wins"],
                "ties": agg["ties"],
                "playoff_meetings": agg["playoff_meetings"],
                "last_meeting": {
                    "season_year": last_meeting["season_year"],
                    "week": last_meeting["week"],
                    "matchup_id": last_meeting["matchup_id"],
                },
                "components": {
                    "balance": round(balance, 3),
                    "tightness": round(tightness, 3),
                    "recency": round(recency, 3),
                    "volume": round(volume, 3),
                    "stakes": round(stakes, 3),
                },
            }
        )

    if not ranked:
        return {"available": False, "reason": "insufficient_rivalry_history"}
    ranked.sort(
        key=lambda r: (
            -r["heat"],
            -r["games"],
            r["owner_a"]["owner_id"],
            r["owner_b"]["owner_id"],
        )
    )
    return {"available": True, "leaderboard": ranked[:top_n]}


def _opp_item(opp: dict[str, Any], names: dict[int, str | None]) -> dict[str, Any]:
    return {
        "opponent": _ref(opp["opponent"], names),
        "games": opp["games"],
        "wins": opp["wins"],
        "losses": opp["losses"],
        "ties": opp["ties"],
        "win_pct": round(opp["win_pct"], 4),
    }


def manager_nemeses(session: Session) -> dict[str, Any]:
    """Per active manager: worst-record opponent and best-record opponent."""
    names = owner_name_map(session)
    active = owner_active_map(session)
    pairs = all_pairwise(session)

    by_owner: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for (low, high), agg in pairs.items():
        games = agg["games"]
        ties = agg["ties"]
        by_owner[low].append(
            {
                "opponent": high,
                "games": games,
                "wins": agg["low_wins"],
                "losses": agg["high_wins"],
                "ties": ties,
                "win_pct": (agg["low_wins"] + 0.5 * ties) / games,
            }
        )
        by_owner[high].append(
            {
                "opponent": low,
                "games": games,
                "wins": agg["high_wins"],
                "losses": agg["low_wins"],
                "ties": ties,
                "win_pct": (agg["high_wins"] + 0.5 * ties) / games,
            }
        )

    managers: list[dict[str, Any]] = []
    for oid in sorted(names):
        if not active.get(oid, True):
            continue
        opps = [o for o in by_owner.get(oid, []) if o["games"] >= MIN_NEMESIS_GAMES]
        nemesis = min(opps, key=lambda o: (o["win_pct"], -o["games"])) if opps else None
        victim = max(opps, key=lambda o: (o["win_pct"], o["games"])) if opps else None
        # With a single qualifying opponent, nemesis and victim collide — keep only
        # the side the record actually supports rather than showing both.
        if nemesis is not None and victim is not None and nemesis["opponent"] == victim["opponent"]:
            if nemesis["win_pct"] <= 0.5:
                victim = None
            else:
                nemesis = None
        managers.append(
            {
                "owner": _ref(oid, names),
                "nemesis": _opp_item(nemesis, names) if nemesis else None,
                "favorite_victim": _opp_item(victim, names) if victim else None,
            }
        )
    return {"available": True, "managers": managers}


def _finals_index(
    session: Session, season_years: set[int]
) -> dict[tuple[int, frozenset[int]], str]:
    """Map ``(season_year, {owner_a, owner_b}) -> final-round label`` from brackets.

    Only the seasons that actually have playoff meetings are walked, so this stays
    cheap. Labels come from ``bracket.py`` ("Championship", "3rd Place", …).
    """
    year_to_id = {
        int(yr): int(sid)
        for sid, yr in session.execute(select(Season.season_id, Season.year)).all()
    }
    index: dict[tuple[int, frozenset[int]], str] = {}
    for year in season_years:
        sid = year_to_id.get(year)
        if sid is None:
            continue
        bracket = season_bracket(session, sid)
        if not bracket or not bracket.get("available"):
            continue
        for key in ("playoff_bracket", "consolation_bracket"):
            section = bracket.get(key)
            if not section:
                continue
            for rnd in section["rounds"]:
                for game in rnd["games"]:
                    label = game.get("game_label")
                    team_a, team_b = game.get("team_a"), game.get("team_b")
                    if not label or not team_a or not team_b:
                        continue
                    oa, ob = team_a.get("owner_id"), team_b.get("owner_id")
                    if oa is None or ob is None:
                        continue
                    index[(year, frozenset({oa, ob}))] = label
    return index


def playoff_rivalries(session: Session, top_n: int = 6) -> dict[str, Any]:
    """Pairs with postseason history: playoff-only record + finals context."""
    names = owner_name_map(session)
    pairs = all_pairwise(session)

    playoff_years: set[int] = {
        mt["season_year"]
        for agg in pairs.values()
        for mt in agg["meetings"]
        if mt["is_playoff"] and mt["season_year"] is not None
    }
    finals = _finals_index(session, playoff_years)

    items: list[dict[str, Any]] = []
    for (low, high), agg in pairs.items():
        pm = [m for m in agg["meetings"] if m["is_playoff"]]
        if not pm:
            continue
        low_wins = sum(1 for m in pm if m["low_margin"] > 0)
        high_wins = sum(1 for m in pm if m["low_margin"] < 0)
        ties = sum(1 for m in pm if m["low_margin"] == 0)
        last = max(pm, key=lambda m: (m["season_year"] or 0, m["week"] or 0))
        finals_meeting: dict[str, Any] | None = None
        for m in sorted(pm, key=lambda x: (x["season_year"] or 0, x["week"] or 0), reverse=True):
            label = finals.get((m["season_year"], frozenset({low, high})))
            if label:
                finals_meeting = {
                    "season_year": m["season_year"],
                    "week": m["week"],
                    "matchup_id": m["matchup_id"],
                    "label": label,
                }
                break
        items.append(
            {
                "owner_a": _ref(low, names),
                "owner_b": _ref(high, names),
                "playoff_meetings": len(pm),
                "a_wins": low_wins,
                "b_wins": high_wins,
                "ties": ties,
                "last_meeting": {
                    "season_year": last["season_year"],
                    "week": last["week"],
                    "matchup_id": last["matchup_id"],
                },
                "finals_meeting": finals_meeting,
            }
        )

    if not items:
        return {"available": False, "reason": "no_playoff_meetings"}
    items.sort(
        key=lambda r: (
            -r["playoff_meetings"],
            0 if r["finals_meeting"] else 1,
            r["owner_a"]["owner_id"],
        )
    )
    return {"available": True, "rivalries": items[:top_n]}


def rivalry_insights(session: Session) -> dict[str, Any]:
    """The bundle that powers the insight bands on ``/rivalries``."""
    return {
        "records": rivalry_records(session),
        "streaks": rivalry_streaks(session),
        "intensity": rivalry_intensity(session),
        "nemeses": manager_nemeses(session),
        "playoffs": playoff_rivalries(session),
    }
