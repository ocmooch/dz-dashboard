"""Caveated postseason bracket surface.

Phase 1 stores matchup rows, not a fully reliable championship/consolation tree.
This module exposes proven post-regular-season games structured as bracket rounds
with derived labels. Consolation is separated when source flags distinguish it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup
from ff_pipeline.repository.queries import get_season, get_team
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks, require_league
from ff_dashboard.analytics.conferences import conference_map
from ff_dashboard.analytics.historical_team_names import period_team_name

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


BRACKET_CAVEAT = (
    "Post-regular-season matchups from the source data. Championship versus consolation "
    "structure is shown only when source flags distinguish it."
)

# Final-round per-game labels for each bracket type
_LABELS: dict[str, dict[str, str]] = {
    "playoff": {
        "championship": "Championship",
        "third": "3rd Place",
        "fifth": "5th Place",
    },
    "consolation": {
        "championship": "7th Place",
        "third": "9th Place",
        "fifth": "11th Place",
    },
}


def _team_ref(
    team_id: int | None,
    score: float | None,
    is_winner: bool,
    cache: dict[int, Any],
    owners: dict[int, str | None],
    session: Session,
    conf_map: dict[int, tuple[int | None, str | None]] | None = None,
) -> dict[str, Any] | None:
    if team_id is None:
        return None
    team = cache.get(team_id)
    if team is None:
        team = get_team(session, team_id)
        cache[team_id] = team
    _conf_name = (conf_map or {}).get(team_id, (None, None))[1]
    return {
        "team_id": team_id,
        "team_name": period_team_name(team) if team is not None else None,
        "owner_id": team.owner_id if team is not None else None,
        "owner_name": owners.get(team.owner_id) if team is not None else None,
        "score": round(score, 2) if score is not None else None,
        "is_winner": is_winner,
        "conference_name": _conf_name,
    }


def _build_bracket_section(
    game_dicts: list[dict[str, Any]],
    bracket_type: str,
) -> dict[str, Any]:
    """Group game_dicts into rounds, derive round/game labels, identify bye teams."""
    if not game_dicts:
        return {"size": 0, "rounds": [], "bye_teams": []}

    by_week: dict[int, list[dict[str, Any]]] = {}
    for g in game_dicts:
        by_week.setdefault(g["week"], []).append(g)
    sorted_weeks = sorted(by_week.keys())
    n_rounds = len(sorted_weeks)

    # Track participants and winners per round number
    r_parts: dict[int, set[int]] = {}
    r_wins: dict[int, set[int]] = {}
    for rnum, week in enumerate(sorted_weeks, 1):
        parts: set[int] = set()
        wins: set[int] = set()
        for g in by_week[week]:
            if g["team_a"]:
                parts.add(g["team_a"]["team_id"])
            if g["team_b"]:
                parts.add(g["team_b"]["team_id"])
            if g["winner_team_id"]:
                wins.add(g["winner_team_id"])
        r_parts[rnum] = parts
        r_wins[rnum] = wins

    # Bye teams: appear in round 2+ but not round 1
    r1 = r_parts.get(1, set())
    all_later: set[int] = set()
    for rnum in range(2, n_rounds + 1):
        all_later |= r_parts[rnum]
    bye_tids = all_later - r1

    # Build bye-team identity refs from game data (include conference_name)
    team_identity: dict[int, dict[str, Any]] = {}
    for games in by_week.values():
        for g in games:
            for side in ("team_a", "team_b"):
                t = g.get(side)
                if t and t["team_id"] not in team_identity:
                    team_identity[t["team_id"]] = {
                        "team_id": t["team_id"],
                        "team_name": t.get("team_name"),
                        "owner_id": t.get("owner_id"),
                        "owner_name": t.get("owner_name"),
                        "conference_name": t.get("conference_name"),
                    }
    bye_teams = [team_identity[tid] for tid in sorted(bye_tids) if tid in team_identity]

    labels = _LABELS[bracket_type]
    rounds: list[dict[str, Any]] = []

    for rnum, week in enumerate(sorted_weeks, 1):
        week_games = [dict(g) for g in by_week[week]]

        # Derive individual game labels for the final round
        if rnum == n_rounds and n_rounds >= 2:
            prev_parts = r_parts.get(n_rounds - 1, set())
            prev_wins = r_wins.get(n_rounds - 1, set())
            for g in week_games:
                tids: set[int] = set()
                if g["team_a"]:
                    tids.add(g["team_a"]["team_id"])
                if g["team_b"]:
                    tids.add(g["team_b"]["team_id"])
                in_prev = tids & prev_parts
                won_prev = tids & prev_wins
                if len(won_prev) == 2:
                    g["game_label"] = labels["championship"]
                elif len(in_prev) == 2 and len(won_prev) == 0:
                    g["game_label"] = labels["third"]
                else:
                    g["game_label"] = labels["fifth"]

        # Round label
        if n_rounds == 1 or rnum == n_rounds:
            round_label = "Finals"
        elif rnum == n_rounds - 1:
            round_label = "Semifinals"
        elif rnum == 1:
            round_label = "First Round"
        else:
            round_label = f"Round {rnum}"

        rounds.append(
            {
                "round_num": rnum,
                "round_label": round_label,
                "bye_teams": bye_teams if rnum == 1 else [],
                "games": week_games,
            }
        )

    all_team_ids: set[int] = set().union(*r_parts.values())
    return {"size": len(all_team_ids), "rounds": rounds, "bye_teams": bye_teams}


def season_bracket(session: Session, season_id: int) -> dict[str, Any] | None:
    """Return structured postseason bracket for ``season_id``; ``None`` when absent."""
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None

    regular_weeks = regular_season_weeks(session, season)
    rows = list(
        session.execute(
            select(Matchup)
            .where(Matchup.season_id == season_id, Matchup.week > regular_weeks)
            .order_by(Matchup.week, Matchup.matchup_id)
        )
        .scalars()
        .all()
    )

    base: dict[str, Any] = {
        "season_id": season_id,
        "season_year": season.year,
        "regular_season_weeks": regular_weeks,
        "caveat": BRACKET_CAVEAT,
    }
    if not rows:
        return {
            **base,
            "available": False,
            "reason": "bracket_unavailable",
            "consolation_distinguished": False,
            "playoff_bracket": None,
            "consolation_bracket": None,
        }

    owners = owner_name_map(session)
    conf_map_data = conference_map(session, season_id)
    cache: dict[int, Any] = {}
    consolation_distinguished = any(bool(m.is_consolation) for m in rows)

    seen: set[tuple[int, frozenset[int]]] = set()
    game_dicts: list[dict[str, Any]] = []
    for m in rows:
        pair = frozenset(
            {m.team_id, m.opponent_team_id} if m.opponent_team_id is not None else {m.team_id}
        )
        key = (m.week, pair)
        if key in seen:
            continue
        seen.add(key)

        winner_team_id: int | None = None
        if (
            m.opponent_team_id is not None
            and m.team_score is not None
            and m.opponent_score is not None
        ):
            if m.team_score > m.opponent_score:
                winner_team_id = m.team_id
            elif m.opponent_score > m.team_score:
                winner_team_id = m.opponent_team_id

        is_consol = bool(m.is_consolation) if consolation_distinguished else None
        game_dicts.append(
            {
                "week": m.week,
                "matchup_id": m.matchup_id,
                "is_playoff": bool(m.is_playoff),
                "is_consolation": is_consol,
                "game_label": None,
                "team_a": _team_ref(
                    m.team_id,
                    m.team_score,
                    winner_team_id == m.team_id,
                    cache,
                    owners,
                    session,
                    conf_map_data,
                ),
                "team_b": _team_ref(
                    m.opponent_team_id,
                    m.opponent_score,
                    winner_team_id == m.opponent_team_id,
                    cache,
                    owners,
                    session,
                    conf_map_data,
                ),
                "winner_team_id": winner_team_id,
            }
        )

    if consolation_distinguished:
        playoff_games = [g for g in game_dicts if g["is_consolation"] is False]
        consol_games = [g for g in game_dicts if g["is_consolation"] is True]
        playoff_bracket = _build_bracket_section(playoff_games, "playoff")
        consol_bracket = _build_bracket_section(consol_games, "consolation")
    else:
        playoff_bracket = _build_bracket_section(game_dicts, "playoff")
        consol_bracket = None

    return {
        **base,
        "available": True,
        "reason": None,
        "consolation_distinguished": consolation_distinguished,
        "playoff_bracket": playoff_bracket,
        "consolation_bracket": consol_bracket,
    }
