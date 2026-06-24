"""Authoritative league scoring helpers (``analytics/scoring.py``).

``player_stats_scored.total_points`` is an independent reconstruction (nflverse
source stats scored by the league's per-season rules); the authoritative,
bonus-inclusive league score is the scraped ``team_rosters.extra_data.nfl_com_points``,
present only on *rostered* player-weeks. The two now agree for the overwhelming
majority of rows — the NFL.com long-TD bonuses were folded into the reconstruction
upstream (danger-zone ``backfill_long_td_bonus.py``) — but a small residual still
diverges: ~69 offensive player-weeks (genuine nflverse-vs-NFL.com *stat*
disagreements, not missing rules) and the DST ``points_allowed`` class (a faithful
PBP re-derivation is still pending — see
``docs/handoffs/dst-points-allowed-rederivation.md``).

Every surface that ranks or sums individual player-weeks must therefore prefer
``nfl_com_points`` and fall back to ``total_points`` — the same coalesce the box
score, player weekly and records book already use (see
:mod:`ff_dashboard.analytics.records`). This module centralises that expression
and the league-relevance ("rostered-ever") filter so the surfaces cannot quietly
diverge again. See ``docs/plans/bonus-scoring-fidelity.md``.

**Why the coalesce is not yet a no-op.** It retires once the reconstruction matches
``nfl_com_points`` everywhere. The offensive gap is effectively closed (its residual
is irreducible source disagreement, not fixable rules); the DST ``points_allowed``
re-derivation is the remaining systematic work. Until then the coalesce keeps every
displayed number authoritative regardless of the residual.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import Player, PlayerStatsScored, TeamRoster
from sqlalchemy import Float, cast, func

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement


def nfl_com_points(roster: type[TeamRoster] = TeamRoster) -> ColumnElement[float]:
    """The scraped, bonus-inclusive NFL.com league points from a roster row's JSON.

    ``NULL`` for a non-rostered week (no matching roster row) or a roster row
    without the key — exactly where :func:`authoritative_week_points` falls back.
    """
    return cast(func.json_extract(roster.extra_data, "$.nfl_com_points"), Float)


def authoritative_week_points(
    roster: type[TeamRoster] = TeamRoster,
    scored: type[PlayerStatsScored] = PlayerStatsScored,
) -> ColumnElement[float]:
    """``coalesce(nfl_com_points, total_points)`` — the league score for one player-week.

    The query must LEFT JOIN ``roster`` on ``(player_id, season_year, week)`` so a
    non-rostered week (no NFL.com JSON) falls back to the reconstruction. There is
    at most one roster row per ``(player_id, season_year, week)``, so the join is
    cardinality-safe for SUM/ORDER BY surfaces.
    """
    return func.coalesce(nfl_com_points(roster), scored.total_points)


def rostered_ever(player: type[Player] = Player) -> ColumnElement[bool]:
    """League-relevance filter: the player held a roster spot at some point in
    league history.

    Reads the pipeline's materialized ``last_rostered_season`` span column — the
    same signal :func:`ff_dashboard.analytics.players.list_player_index` uses to
    scope the players view. The reconstruction scores the whole NFL, so "scored"
    is not a relevance signal; "ever rostered" is (owner decision, see the plan).
    """
    return player.last_rostered_season.is_not(None)
