"""Global typeahead search across owners, seasons, and players.

League-scoped. Ranks prefix matches above substring matches, and entity types
owner > season > player so the most navigationally useful hits surface first.
Teams are deliberately excluded: the SPA has no standalone team page, so a team
hit would be a dead deep-link — owner search already covers team-name intent for
this single league.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Owner, Season
from ff_pipeline.repository.queries import search_players
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Entity-type ordering: owners are the most useful nav target, then seasons, then players.
_TYPE_RANK = {"owner": 0, "season": 1, "player": 2}


def _match_rank(haystack: str, needle: str) -> int | None:
    """0 = prefix match, 1 = substring match, None = no match (case-insensitive)."""
    h = haystack.casefold()
    n = needle.casefold()
    if h.startswith(n):
        return 0
    if n in h:
        return 1
    return None


def global_search(session: Session, q: str, limit: int = 10) -> list[dict[str, Any]]:
    """Ranked typeahead hits for ``q`` across owners, seasons, and players.

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

    # Players -> /players/{player_id}. Reuse the repository's name search (case-insensitive
    # substring); fall back to a substring rank if our own check is stricter than ilike.
    for player in search_players(session, name=query, limit=limit):
        name = player.name_full or ""
        rank = _match_rank(name, query)
        if rank is None:
            rank = 1
        bits = [b for b in (player.position, player.nfl_team) if b]
        scored.append(
            (
                rank,
                _TYPE_RANK["player"],
                name.casefold(),
                {
                    "type": "player",
                    "id": int(player.player_id),
                    "label": name or f"Player {player.player_id}",
                    "sublabel": " · ".join(bits) if bits else "Player",
                    "href": f"/players/{player.player_id}",
                },
            )
        )

    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    return [hit for _, _, _, hit in scored[:limit]]
