"""P10 — global-search unit tests against the known-answer fixture.

Verifies prefix-over-substring ranking, owner > season > player type ordering,
the deep-link hrefs each hit carries, the honest empty result for a blank or
no-match query, and that teams are deliberately never emitted.
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
    players = _of_type(global_search(session, "jeff"), "player")
    jjet = next(h for h in players if h["label"] == "Justin Jefferson")
    assert jjet["id"] == KNOWN["player_id"]["jjet"]
    assert jjet["href"] == f"/players/{KNOWN['player_id']['jjet']}"
    assert jjet["sublabel"] == "WR · MIN"


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


def test_teams_are_never_emitted(session: Session) -> None:
    # Team names are "Maverick 2016" etc.; search must not deep-link to a dead team page.
    assert all(h["type"] != "team" for h in global_search(session, "Maverick"))


def test_blank_query_is_empty(session: Session) -> None:
    assert global_search(session, "   ") == []


def test_no_match_is_empty(session: Session) -> None:
    assert global_search(session, "zzzznomatch") == []


def test_limit_is_respected(session: Session) -> None:
    assert len(global_search(session, "Ice", limit=1)) <= 1
