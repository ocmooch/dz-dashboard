"""Caveated postseason bracket surface.

Phase 1 stores matchup rows, not a fully reliable championship/consolation tree.
This module exposes proven post-regular-season games structured as bracket rounds
with derived labels. The main (championship) and consolation brackets are separated
by their connected components in the post-season matchup graph: the two halves of a
placement bracket never play each other, so connectivity partitions them cleanly with
no hardcoded seed threshold. The component with the better (lower) final ranks is the
championship bracket; the other is consolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Season, Team
from ff_pipeline.repository.queries import get_season, get_team
from sqlalchemy import select

from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks, require_league
from ff_dashboard.analytics.conferences import conference_map
from ff_dashboard.analytics.historical_team_names import period_team_name

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


BRACKET_CAVEAT = (
    "Post-regular-season matchups from the source data. The championship and consolation "
    "brackets are separated by who actually played whom, not by source flags."
)

# Three-way postseason game tiers used by the shared classifier (Part A). The
# championship is the single title game; the rest of the winners' bracket is
# ``playoff``; the placement/"toilet" half is ``consolation``.
TIER_CHAMPIONSHIP = "championship"
TIER_PLAYOFF = "playoff"
TIER_CONSOLATION = "consolation"

CHAMPIONSHIP_GAME_LABEL = "Championship"
TOILET_BOWL_GAME_LABEL = "Toilet Bowl"

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
        "is_sacko": False,  # set on the toilet-bowl loser below
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


def _connected_components(game_dicts: list[dict[str, Any]]) -> list[set[int]]:
    """Partition post-season teams into brackets via matchup connectivity.

    In a placement bracket the championship and consolation halves never play each
    other across any round, so the connected components of the "played-against"
    graph are exactly the separate brackets. Returns one ``set`` of team ids per
    component, deterministically ordered by smallest member id.
    """
    adj: dict[int, set[int]] = {}
    for g in game_dicts:
        a = g["team_a"]["team_id"] if g["team_a"] else None
        b = g["team_b"]["team_id"] if g["team_b"] else None
        if a is not None:
            adj.setdefault(a, set())
        if b is not None:
            adj.setdefault(b, set())
        if a is not None and b is not None:
            adj[a].add(b)
            adj[b].add(a)

    seen: set[int] = set()
    components: list[set[int]] = []
    for node in sorted(adj):
        if node in seen:
            continue
        stack = [node]
        comp: set[int] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.add(cur)
            stack.extend(adj[cur] - seen)
        components.append(comp)
    return components


def _order_components(
    components: list[set[int]], final_ranks: dict[int, int | None]
) -> list[set[int]]:
    """Order brackets best-first: the championship half (lowest final ranks) leads.

    Ties / missing ranks fall back to the smallest team id so the order stays stable.
    """

    def sort_key(comp: set[int]) -> tuple[int, int]:
        ranks = [r for r in (final_ranks.get(t) for t in comp) if r is not None]
        min_rank = min(ranks) if ranks else 10**6
        return (min_rank, min(comp))

    return sorted(components, key=sort_key)


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

        game_dicts.append(
            {
                "week": m.week,
                "matchup_id": m.matchup_id,
                "is_playoff": bool(m.is_playoff),
                "is_consolation": None,  # assigned below from bracket membership
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

    # Flag the Sacko (toilet-bowl loser) on their team ref in that game, so the
    # bracket can surface the 💩 anti-trophy. Reuses the shared classifier so the
    # toilet-bowl identification stays in one place; the deduped game's id equals
    # the classifier's ``matchup_id`` (both the smallest of the pair's two rows).
    sacko = postseason_classification(session, season_id).get("sacko") or {}
    sacko_mid = sacko.get("matchup_id")
    sacko_tid = sacko.get("team_id")
    if sacko_mid is not None and sacko_tid is not None:
        for g in game_dicts:
            if g["matchup_id"] != sacko_mid:
                continue
            for side in ("team_a", "team_b"):
                ref = g.get(side)
                if ref is not None and ref["team_id"] == sacko_tid:
                    ref["is_sacko"] = True

    # Split the championship and consolation halves by matchup connectivity, then
    # label the lower-ranked half as the championship bracket. final_rank is read
    # from the cached Team rows fetched while building game_dicts.
    final_ranks: dict[int, int | None] = {}
    for tid in cache:
        team = cache[tid]
        final_ranks[tid] = getattr(team, "final_rank", None) if team is not None else None

    components = _order_components(_connected_components(game_dicts), final_ranks)
    consolation_distinguished = len(components) >= 2

    if consolation_distinguished:
        # components[0] is the championship half; everything after is consolation.
        consol_ids: set[int] = set().union(*components[1:])
        playoff_games: list[dict[str, Any]] = []
        consol_games: list[dict[str, Any]] = []
        for g in game_dicts:
            a_id = g["team_a"]["team_id"] if g["team_a"] else None
            is_consol = a_id in consol_ids if a_id is not None else False
            g["is_consolation"] = is_consol
            (consol_games if is_consol else playoff_games).append(g)
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


def _empty_classification(season_id: int, season_year: int | None) -> dict[str, Any]:
    return {
        "season_id": season_id,
        "season_year": season_year,
        "consolation_distinguished": False,
        "by_matchup_id": {},
        "championship_matchup_id": None,
        "sacko": None,
    }


def postseason_classification(session: Session, season_id: int) -> dict[str, Any]:
    """Shared three-way postseason classifier (the keystone for Part A).

    Reuses the same connectivity split as :func:`season_bracket`
    (``_connected_components`` + ``_order_components``) so every consumer agrees on
    which games are championship / playoff / consolation. Returns:

    * ``by_matchup_id`` — ``{matchup_id: {"tier", "game_label"}}`` for **both** stored
      rows of every postseason game, so a consumer can classify by either row's id.
    * ``championship_matchup_id`` — the title game, anchored on ``Season.champion_team_id``
      (the playoff-half final whose winner is the champion). ``None`` when it can't be
      proven (e.g. several finals share the last week and none is the champion).
    * ``sacko`` — the **toilet-bowl final loser** (derived). Falls back to the recorded
      ``Season.last_place_team_id`` (``source:"recorded"``) where the consolation bracket
      can't be distinguished; ``None`` when neither is available.

    Honesty: where ``consolation_distinguished`` is False, no game is tagged
    ``consolation`` and no Sacko is *derived* — those stay generic / fall back, never
    fabricated.
    """
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return _empty_classification(season_id, None)

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
    if not rows:
        return _empty_classification(season_id, season.year)

    # One unit per distinct game; track both stored rows' matchup_ids so the tier
    # map covers whichever row a consumer holds.
    units: dict[tuple[int, frozenset[int]], dict[str, Any]] = {}
    for m in rows:
        if m.opponent_team_id is None:
            continue  # a postseason bye carries no bracket edge
        pair = frozenset({m.team_id, m.opponent_team_id})
        key = (m.week, pair)
        unit = units.get(key)
        if unit is None:
            winner: int | None = None
            if m.team_score is not None and m.opponent_score is not None:
                if m.team_score > m.opponent_score:
                    winner = m.team_id
                elif m.opponent_score > m.team_score:
                    winner = m.opponent_team_id
            unit = {
                "week": m.week,
                "team_a": {"team_id": m.team_id},
                "team_b": {"team_id": m.opponent_team_id},
                "winner_team_id": winner,
                "matchup_ids": [],
            }
            units[key] = unit
        unit["matchup_ids"].append(m.matchup_id)

    games = list(units.values())
    if not games:
        return _empty_classification(season_id, season.year)

    team_ids: set[int] = set()
    for u in games:
        team_ids.add(u["team_a"]["team_id"])
        team_ids.add(u["team_b"]["team_id"])
    teams = {
        int(t.team_id): t
        for t in session.execute(select(Team).where(Team.team_id.in_(team_ids))).scalars().all()
    }
    final_ranks = {tid: getattr(t, "final_rank", None) for tid, t in teams.items()}

    components = _order_components(_connected_components(games), final_ranks)
    consolation_distinguished = len(components) >= 2
    consol_ids: set[int] = set().union(*components[1:]) if consolation_distinguished else set()

    by_matchup_id: dict[int, dict[str, Any]] = {}
    for u in games:
        a_id = u["team_a"]["team_id"]
        tier = TIER_CONSOLATION if a_id in consol_ids else TIER_PLAYOFF
        u["tier"] = tier
        for mid in u["matchup_ids"]:
            by_matchup_id[mid] = {"tier": tier, "game_label": None}

    # Championship: the playoff-half final (latest playoff week) whose winner is the
    # recorded champion. Authoritative anchor; left None when unprovable.
    championship_matchup_id: int | None = None
    playoff_games = [u for u in games if u["tier"] == TIER_PLAYOFF]
    champ_team_id = season.champion_team_id
    if playoff_games:
        last_week = max(u["week"] for u in playoff_games)
        finals = [u for u in playoff_games if u["week"] == last_week]
        title = None
        if champ_team_id is not None:
            title = next((u for u in finals if u["winner_team_id"] == champ_team_id), None)
        if title is None and len(finals) == 1:
            title = finals[0]
        if title is not None:
            championship_matchup_id = sorted(title["matchup_ids"])[0]
            for mid in title["matchup_ids"]:
                by_matchup_id[mid] = {
                    "tier": TIER_CHAMPIONSHIP,
                    "game_label": CHAMPIONSHIP_GAME_LABEL,
                }

    # Sacko: loser of the toilet-bowl game (the consolation final whose participants
    # hold the worst final ranks). Falls back to the recorded last-place team.
    sacko: dict[str, Any] | None = None
    if consolation_distinguished:
        consol_games = [u for u in games if u["tier"] == TIER_CONSOLATION]
        if consol_games:
            last_cw = max(u["week"] for u in consol_games)
            consol_finals = [u for u in consol_games if u["week"] == last_cw]

            def _worst_rank(u: dict[str, Any]) -> int:
                ranks = [
                    final_ranks.get(u["team_a"]["team_id"]),
                    final_ranks.get(u["team_b"]["team_id"]),
                ]
                present = [r for r in ranks if r is not None]
                return max(present) if present else -1

            toilet = max(consol_finals, key=_worst_rank)
            if toilet["winner_team_id"] is not None:
                a_id = toilet["team_a"]["team_id"]
                b_id = toilet["team_b"]["team_id"]
                loser = b_id if toilet["winner_team_id"] == a_id else a_id
                loser_team = teams.get(loser)
                sacko = {
                    "team_id": loser,
                    "owner_id": loser_team.owner_id if loser_team is not None else None,
                    "matchup_id": sorted(toilet["matchup_ids"])[0],
                    "season_year": season.year,
                    "source": "derived",
                }
                for mid in toilet["matchup_ids"]:
                    by_matchup_id[mid]["game_label"] = TOILET_BOWL_GAME_LABEL
    if sacko is None and season.last_place_team_id is not None:
        lp = teams.get(int(season.last_place_team_id))
        if lp is None:
            lp = get_team(session, int(season.last_place_team_id))
        sacko = {
            "team_id": int(season.last_place_team_id),
            "owner_id": lp.owner_id if lp is not None else None,
            "matchup_id": None,
            "season_year": season.year,
            "source": "recorded",
        }

    return {
        "season_id": season_id,
        "season_year": season.year,
        "consolation_distinguished": consolation_distinguished,
        "by_matchup_id": by_matchup_id,
        "championship_matchup_id": championship_matchup_id,
        "sacko": sacko,
    }


def season_sacko_map(session: Session) -> dict[int, dict[str, Any]]:
    """``{season_id: sacko}`` across every season that has a derivable/recorded Sacko.

    One classification per season; consumers (owners, teams, records, league
    history) share this instead of re-deriving the bracket split.
    """
    result: dict[int, dict[str, Any]] = {}
    for sid in session.execute(select(Season.season_id)).scalars().all():
        sacko = postseason_classification(session, int(sid)).get("sacko")
        if sacko is not None:
            result[int(sid)] = sacko
    return result
