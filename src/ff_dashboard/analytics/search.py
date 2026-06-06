"""Global typeahead search across owners, fantasy teams, seasons, and players.

League-scoped. Ranks prefix matches above substring matches, and entity types
owner > team > season > player so the most navigationally useful hits surface
first. The player branch is filtered to league-relevant players (ever rostered),
mirroring the player index — a never-rostered nflverse "ghost" never appears.

Two team affordances:
- **Fantasy team names** resolve to the owner who held them (no standalone team
  page) — a real deep-link, not a dead one.
- **NFL team tokens** (city / nickname / abbreviation) are a query *expander*:
  they pull that team's league-relevant players, but get no standalone hit.

Input hardening: candidate names from Phase-1 ``search_players`` (whose ``ilike``
treats ``%``/``_`` as SQL LIKE wildcards) are re-filtered through ``_match_rank``,
a plain casefold ``startswith``/``in`` check with no ``re``. So wildcard and regex
metacharacters are neutralised dashboard-side — treated as literal data — without
modifying the read-only Phase-1 query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Owner, Season, Team
from ff_pipeline.repository.queries import search_players
from sqlalchemy import select

from ff_dashboard.analytics.nfl_teams import resolve_nfl_teams

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Player
    from sqlalchemy.orm import Session

# Entity-type ordering: owners and fantasy teams are the most useful nav targets
# (both deep-link to a manager), then seasons, then players.
_TYPE_RANK = {"owner": 0, "team": 1, "season": 2, "player": 3}


def _match_rank(haystack: str, needle: str) -> int | None:
    """0 = prefix match, 1 = substring match, None = no match (case-insensitive)."""
    h = haystack.casefold()
    n = needle.casefold()
    if h.startswith(n):
        return 0
    if n in h:
        return 1
    return None


def _player_hit(player: Player) -> dict[str, Any]:
    name = player.name_full or ""
    bits = [b for b in (player.position, player.nfl_team) if b]
    return {
        "type": "player",
        "id": int(player.player_id),
        "label": name or f"Player {player.player_id}",
        "sublabel": " · ".join(bits) if bits else "Player",
        "href": f"/players/{player.player_id}",
    }


def global_search(session: Session, q: str, limit: int = 10) -> list[dict[str, Any]]:
    """Ranked typeahead hits for ``q`` across owners, fantasy teams, seasons, players.

    Each hit is ``{type, id, label, sublabel, href}``. Sorted by match quality
    (prefix before substring), then entity type, then label — so the best
    navigational target is first. Returns ``[]`` for a blank query.
    """
    query = q.strip()
    if not query:
        return []

    scored: list[tuple[int, int, str, dict[str, Any]]] = []

    # Owners -> /managers/{owner_id}
    for owner in session.execute(select(Owner)).scalars():
        name = owner.display_name or ""
        rank = _match_rank(name, query)
        if rank is not None:
            scored.append(
                (
                    rank,
                    _TYPE_RANK["owner"],
                    name.casefold(),
                    {
                        "type": "owner",
                        "id": int(owner.owner_id),
                        "label": name or f"Manager {owner.owner_id}",
                        "sublabel": "Manager",
                        "href": f"/managers/{owner.owner_id}",
                    },
                )
            )

    # Fantasy teams -> the owner who held the name (no team page). Collapse a
    # team_name reused across seasons/owners to its most-recent owner: one hit
    # per distinct name, keyed by casefolded name.
    team_matches: dict[str, tuple[int, int, dict[str, Any]]] = {}  # name -> (year, rank, hit)
    for team in session.execute(select(Team)).scalars():
        team_name = team.team_name or ""
        rank = _match_rank(team_name, query)
        if rank is None:
            continue
        year = int(team.season.year)
        key = team_name.casefold()
        prev = team_matches.get(key)
        if prev is None or year > prev[0]:
            team_matches[key] = (
                year,
                rank,
                {
                    "type": "team",
                    "id": int(team.owner_id),
                    "label": team_name,
                    "sublabel": f"Fantasy team · {year}",
                    "href": f"/managers/{team.owner_id}",
                },
            )
    for key, (_, rank, hit) in team_matches.items():
        scored.append((rank, _TYPE_RANK["team"], key, hit))

    # Seasons -> /standings (the season context switches client-side); match on year text.
    for season in session.execute(select(Season).order_by(Season.year.desc())).scalars():
        year_text = str(season.year)
        rank = _match_rank(year_text, query)
        if rank is not None:
            scored.append(
                (
                    rank,
                    _TYPE_RANK["season"],
                    year_text,
                    {
                        "type": "season",
                        "id": int(season.season_id),
                        "label": f"{season.year} season",
                        "sublabel": "Standings",
                        "href": "/standings",
                    },
                )
            )

    # Players -> /players/{player_id}. League-scoped (ever rostered). Re-filter the
    # repository's ilike candidates through _match_rank so SQL LIKE wildcards and
    # regex metachars in the query stay literal (input hardening).
    seen_players: set[int] = set()
    for player in search_players(session, name=query, league_relevant=True, limit=limit):
        name = player.name_full or ""
        rank = _match_rank(name, query)
        if rank is None:
            continue
        seen_players.add(int(player.player_id))
        scored.append((rank, _TYPE_RANK["player"], name.casefold(), _player_hit(player)))

    # NFL-team query expander: a city/nickname/abbrev token surfaces that team's
    # league-relevant players (deduped against the name branch). The NFL team
    # itself gets no hit — there is no NFL-team page.
    for abbrev in resolve_nfl_teams(query):
        for player in search_players(session, nfl_team=abbrev, league_relevant=True, limit=limit):
            pid = int(player.player_id)
            if pid in seen_players:
                continue
            seen_players.add(pid)
            name = player.name_full or ""
            scored.append((1, _TYPE_RANK["player"], name.casefold(), _player_hit(player)))

    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    return [hit for _, _, _, hit in scored[:limit]]
