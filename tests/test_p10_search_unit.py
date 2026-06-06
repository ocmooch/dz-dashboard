"""P10 — global-search unit tests against the known-answer fixture.

Verifies prefix-over-substring ranking, owner > team > season > player type
ordering, the deep-link hrefs each hit carries, the honest empty result for a
blank or no-match query, that a fantasy team name deep-links to its owner, and
that an NFL-team token expands to players without a standalone team hit.
(The scope/synonym/hardening suite lives in tests/test_search.py.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_dashboard.analytics.search import global_search
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _of_type(hits: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [h for h in hits if h["type"] == kind]


def test_owner_prefix_match(session: Session) -> None:
    owners = _of_type(global_search(session, "Mav"), "owner")
    mav = next(h for h in owners if h["label"] == "Maverick")
    assert mav["id"] == KNOWN["owner_id"]["mav"]
    assert mav["href"] == f"/managers/{KNOWN['owner_id']['mav']}"
    assert mav["sublabel"] == "Manager"


def test_player_substring_match(session: Session) -> None:
    # cmc is league-relevant (rostered); the like-named ghost "Ghost McCaffrey" is
    # never rostered, so league-scoped search returns only cmc (F-44).
    players = _of_type(global_search(session, "McCaff"), "player")
    cmc = next(h for h in players if h["label"] == "Christian McCaffrey")
    assert cmc["id"] == KNOWN["player_id"]["cmc"]
    assert cmc["href"] == f"/players/{KNOWN['player_id']['cmc']}"
    assert cmc["sublabel"] == "RB · SF"
    assert all(h["label"] != "Ghost McCaffrey" for h in players)


def test_season_year_match(session: Session) -> None:
    seasons = _of_type(global_search(session, "2016"), "season")
    s = next(h for h in seasons if h["label"] == "2016 season")
    assert s["id"] == KNOWN["season_id"][2016]
    assert s["href"] == "/standings"  # season context switches client-side


def test_prefix_owner_outranks_substring_players(session: Session) -> None:
    # "ice" prefixes the owner "Iceman" (rank 0, type owner) and also matches the
    # box-score "Ice ..." players; the owner must surface first.
    hits = global_search(session, "ice")
    assert hits, "expected at least one hit"
    assert hits[0]["type"] == "owner"
    assert hits[0]["label"] == "Iceman"


def test_fantasy_team_name_emits_owner_hit(session: Session) -> None:
    # A distinctive fantasy team name now *is* searchable and deep-links to the
    # owner who held it (no dead team page). See tests/test_search.py for the full
    # F-45 suite; this guards the type ordering lands a team hit at all.
    teams = _of_type(global_search(session, "Northvale"), "team")
    hit = next(h for h in teams if h["label"] == "Northvale Scumbags")
    assert hit["id"] == KNOWN["owner_id"]["viper"]
    assert hit["href"] == f"/managers/{KNOWN['owner_id']['viper']}"


def test_nfl_team_token_emits_no_standalone_team_hit(session: Session) -> None:
    # An NFL-team token expands into players; the NFL team itself never gets a hit.
    assert all(h["type"] != "team" for h in global_search(session, "49ers"))


def test_blank_query_is_empty(session: Session) -> None:
    assert global_search(session, "   ") == []


def test_no_match_is_empty(session: Session) -> None:
    assert global_search(session, "zzzznomatch") == []


def test_limit_is_respected(session: Session) -> None:
    assert len(global_search(session, "Ice", limit=1)) <= 1
