"""Authoritative league scoring helpers (``analytics/scoring.py``).

``player_stats_scored.total_points`` is an independent reconstruction (nflverse
source stats scored by the league's per-season rules); the authoritative,
bonus-inclusive league score is the platform's official per-player value on the roster
row (``extra_data.nfl_com_points`` for NFL.com seasons, ``extra_data.platform_points`` for
Sleeper seasons), present only on *rostered* player-weeks. The two now agree for the overwhelming
majority of rows — the NFL.com long-TD bonuses were folded into the reconstruction
upstream (danger-zone ``backfill_long_td_bonus.py``) — but a small residual still
diverges: ~69 offensive player-weeks (genuine nflverse-vs-NFL.com *stat*
disagreements, not missing rules) and the DST ``points_allowed`` class (a faithful
PBP re-derivation is still pending — see
``docs/handoffs/dst-points-allowed-rederivation.md``).

Every surface that ranks or sums individual player-weeks must therefore prefer the
official points and fall back to ``total_points`` — the same coalesce the box
score, player weekly and records book already use (see
:mod:`ff_dashboard.analytics.records`). This module centralises that expression
and the league-relevance ("rostered-ever") filter so the surfaces cannot quietly
diverge again. See ``docs/plans/bonus-scoring-fidelity.md``. The expressions are aliases
over the upstream source-neutral helpers (``ff_pipeline.repository.queries``; Sleeper D2,
``docs/plans/sleeper-d2-source-neutral-points.md``): nothing here reads a platform's key
directly except the one dict-side mirror, :func:`official_points_from_extra`.

**Why the coalesce is not yet a no-op.** It retires once the reconstruction matches
``nfl_com_points`` everywhere. The offensive gap is effectively closed (its residual
is irreducible source disagreement, not fixable rules); the DST ``points_allowed``
re-derivation is the remaining systematic work. Until then the coalesce keeps every
displayed number authoritative regardless of the residual.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries
from ff_pipeline.repository.models import Player, PlayerStatsScored, TeamRoster

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

# The roster-row JSON keys that hold a platform's official per-player points, in
# precedence order. This mirrors ``queries.official_slot_points_expr`` (Sleeper
# ``platform_points``, else NFL.com ``nfl_com_points``) for code that already holds
# the row's ``extra_data`` dict; a test pins the two to the same answer.
_OFFICIAL_POINTS_KEYS = ("platform_points", "nfl_com_points")


def official_points(roster: type[TeamRoster] = TeamRoster) -> ColumnElement[float]:
    """The platform's official points for a roster row (``NULL`` when it has none).

    Delegates to the upstream ``queries.official_slot_points_expr``, so a Sleeper row
    (``platform_points``) and an NFL.com row (``nfl_com_points``) read the same way.
    """
    return queries.official_slot_points_expr(roster)


def official_points_from_extra(extra: Any) -> float | None:
    """:func:`official_points` for a roster row's already-loaded ``extra_data`` dict.

    Returns ``None`` when no official value is present (the caller then falls back
    to the reconstruction). Non-numeric values, including booleans, count as absent.
    """
    if not isinstance(extra, dict):
        return None
    for key in _OFFICIAL_POINTS_KEYS:
        value = extra.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def authoritative_week_points(
    roster: type[TeamRoster] = TeamRoster,
    scored: type[PlayerStatsScored] = PlayerStatsScored,
) -> ColumnElement[float]:
    """The league score for one player-week: official points, else the reconstruction.

    Delegates to the upstream ``queries.authoritative_week_points_expr``
    (``coalesce(platform_points, nfl_com_points, total_points)``). Upstream proved it
    identical to the old NFL.com-only coalesce on every legacy roster row.

    The query must LEFT JOIN ``roster`` on ``(player_id, season_year, week)`` so a
    non-rostered week (no official JSON) falls back to the reconstruction. There is
    at most one roster row per ``(player_id, season_year, week)``, so the join is
    cardinality-safe for SUM/ORDER BY surfaces.
    """
    return queries.authoritative_week_points_expr(roster, scored)


def rostered_ever(player: type[Player] = Player) -> ColumnElement[bool]:
    """League-relevance filter: the player held a roster spot at some point in
    league history.

    Reads the pipeline's materialized ``last_rostered_season`` span column — the
    same signal :func:`ff_dashboard.analytics.players.list_player_index` uses to
    scope the players view. The reconstruction scores the whole NFL, so "scored"
    is not a relevance signal; "ever rostered" is (owner decision, see the plan).
    """
    return player.last_rostered_season.is_not(None)
