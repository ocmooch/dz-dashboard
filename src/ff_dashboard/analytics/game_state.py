"""One game-state rule for every surface (Sleeper D3).

A matchup row is a *game* only when it has an opponent: idle postseason rows (byes, already placed)
carry a real score but no opponent. A game is *pending* while the weekly capture has not finalized
its week (``extra_data.finalized`` is false). The user's rule (``docs/sleeper/00`` §3): a pending
week is unscored. It is never a tie or any result and adds nothing to standings, PF/PA, records or
head-to-head; it joins once the capture resolves it.

Legacy (NFL.com) rows carry no ``finalized`` key, so they are always final and legacy output is
unchanged. Pure functions over a ``Matchup``-like object; no database access.
"""

from __future__ import annotations

from typing import Any, Literal

Result = Literal["W", "L", "T"]


def _extra(m: Any) -> dict[str, Any]:
    return getattr(m, "extra_data", None) or {}


def is_game(m: Any) -> bool:
    """Has an opponent. Idle postseason rows (``postseason_role`` bye/placed) are not games."""
    return getattr(m, "opponent_team_id", None) is not None


def is_idle(m: Any) -> bool:
    """An idle postseason team-week (Sleeper bye / already placed): a real score, no game."""
    return not is_game(m) and _extra(m).get("postseason_role") is not None


def is_pending(m: Any) -> bool:
    """The week is unfinished and unscored (Sleeper only; legacy rows are never pending)."""
    return _extra(m).get("finalized") is False


def is_final_game(m: Any) -> bool:
    return is_game(m) and not is_pending(m)


def game_result(m: Any) -> Result | None:
    """W / L / T for a final game; ``None`` for a pending week, an idle row or an unplayed week."""
    if is_pending(m):
        return None
    if m.is_win is True:
        return "W"
    if m.is_win is False:
        return "L"
    if m.team_score is not None and m.opponent_score is not None:
        return "T"
    return None


def official_score(m: Any) -> dict[str, float | None]:
    """The commissioner override, if any: ``{official, custom}``.

    ``custom`` is set only when the commissioner awarded a score (``custom_points``). Then
    ``team_score`` is the awarded score and ``official`` is Sleeper's computed total.
    """
    extra = _extra(m)
    custom = extra.get("custom_points")
    official = extra.get("points_official")
    return {
        "official": float(official) if official is not None else None,
        "custom": float(custom) if custom is not None else None,
    }


def commissioner_override(m: Any) -> dict[str, float] | None:
    """``{official, custom}`` when a commissioner override changed the score, else ``None``."""
    s = official_score(m)
    if s["custom"] is None or s["official"] is None:
        return None
    return {"official": s["official"], "custom": s["custom"]}


#: Sleeper weeks with no archived IR list put every non-starter in ``BN`` (00 §4).
BENCH_OR_RESERVE = "bench_or_reserve"


def slot_note(roster_extra: dict[str, Any] | None) -> str | None:
    """``"bench_or_reserve"`` when the bench slot may really be a reserve (IR) slot, else None."""
    certainty = (roster_extra or {}).get("slot_certainty")
    return BENCH_OR_RESERVE if certainty == BENCH_OR_RESERVE else None
