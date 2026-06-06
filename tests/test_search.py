"""fix-pass P3 — search scope, team affordances, and input hardening.

Covers the three P3 findings against the known-answer fixture:

* **F-44** — the player branch is league-scoped: a never-rostered "ghost" never
  appears, while a like-named rostered player does.
* **F-45** — NFL-team tokens (city / nickname / abbreviation) expand into that
  team's *league-relevant* players; fantasy team names deep-link to their owner
  (deduped to the most-recent owner); the NFL team itself gets no standalone hit.
* **F-47** — hostile/odd input (SQL LIKE wildcards, injection, regex metachars,
  ``<script>``, blank/whitespace) is treated as inert data: no crash, no
  over-match, no injection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_dashboard.analytics.nfl_teams import resolve_nfl_teams
from ff_dashboard.analytics.search import global_search
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _of_type(hits: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [h for h in hits if h["type"] == kind]


def _labels(hits: list[dict[str, Any]]) -> set[str]:
    return {h["label"] for h in hits}


# --- F-44: league scope --------------------------------------------------------


def test_search_excludes_never_rostered(session: Session) -> None:
    # "McCaffrey" matches both the rostered cmc and the never-rostered ghost; only
    # the rostered one survives the league scope, mirroring list_player_index.
    players = _of_type(global_search(session, "McCaffrey"), "player")
    labels = _labels(players)
    assert "Christian McCaffrey" in labels
    assert "Ghost McCaffrey" not in labels


def test_scored_but_never_rostered_player_excluded(session: Session) -> None:
    # jjet is scored yet never rostered (the index scope example) — a name query
    # must not surface him now that search is league-scoped.
    players = _of_type(global_search(session, "Jefferson"), "player")
    assert "Justin Jefferson" not in _labels(players)


# --- F-45: NFL-team synonyms + players-by-team ---------------------------------


def test_resolve_nfl_team_synonyms() -> None:
    assert resolve_nfl_teams("49ers") == ["SF"]
    assert resolve_nfl_teams("San Francisco") == ["SF"]
    assert resolve_nfl_teams("SF") == ["SF"]
    assert resolve_nfl_teams("vikings") == ["MIN"]
    assert resolve_nfl_teams("new york") == ["NYG", "NYJ"]
    assert resolve_nfl_teams("Atlantis") == []


def test_nfl_team_by_nickname(session: Session) -> None:
    players = _of_type(global_search(session, "49ers"), "player")
    assert "Christian McCaffrey" in _labels(players)


def test_nfl_team_by_city(session: Session) -> None:
    players = _of_type(global_search(session, "San Francisco"), "player")
    assert "Christian McCaffrey" in _labels(players)


def test_nfl_team_by_abbrev(session: Session) -> None:
    players = _of_type(global_search(session, "SF"), "player")
    cmc = next(h for h in players if h["label"] == "Christian McCaffrey")
    assert cmc["id"] == KNOWN["player_id"]["cmc"]
    assert cmc["href"] == f"/players/{KNOWN['player_id']['cmc']}"


def test_nfl_team_players_are_league_scoped(session: Session) -> None:
    # SF has a never-rostered ghost; the team expander must not surface it.
    players = _of_type(global_search(session, "San Francisco"), "player")
    assert "Ghost McCaffrey" not in _labels(players)
    # MIN's only player (jjet) is never rostered → no league-relevant MIN player.
    min_players = _of_type(global_search(session, "Minnesota"), "player")
    assert "Justin Jefferson" not in _labels(min_players)


def test_nfl_team_no_standalone_hit(session: Session) -> None:
    # The NFL team is a query expander, not a destination.
    assert _of_type(global_search(session, "49ers"), "team") == []


def test_unknown_team_token_no_crash(session: Session) -> None:
    # An unrecognised "team" token resolves to nothing and just returns name hits.
    hits = global_search(session, "Atlantis")
    assert hits == []


# --- F-45: fantasy team names --------------------------------------------------


def test_fantasy_team_name_match(session: Session) -> None:
    teams = _of_type(global_search(session, "Northvale"), "team")
    hit = next(h for h in teams if h["label"] == "Northvale Scumbags")
    assert hit["id"] == KNOWN["owner_id"]["viper"]
    assert hit["href"] == f"/managers/{KNOWN['owner_id']['viper']}"
    assert hit["sublabel"] == "Fantasy team · 2017"


def test_fantasy_team_dedup_recent_owner(session: Session) -> None:
    # "Dynasty Crew" was held by Slider in 2015 and Goose in 2016 → one hit, the
    # most-recent owner (Goose, 2016).
    teams = _of_type(global_search(session, "Dynasty Crew"), "team")
    dynasty = [h for h in teams if h["label"] == "Dynasty Crew"]
    assert len(dynasty) == 1
    assert dynasty[0]["id"] == KNOWN["owner_id"]["goose"]
    assert dynasty[0]["sublabel"] == "Fantasy team · 2016"


def test_team_hit_outranks_season_and_player(session: Session) -> None:
    # type order is owner > team > season > player.
    hits = global_search(session, "Northvale")
    assert hits[0]["type"] == "team"


# --- F-47: input hardening / security ------------------------------------------


def test_like_wildcards_are_literal(session: Session) -> None:
    # Phase-1 ilike treats %/_ as wildcards; re-filtering keeps them literal, so a
    # bare wildcard yields no full-table dump.
    assert global_search(session, "%") == []
    assert global_search(session, "_") == []
    assert global_search(session, "%%%") == []


def test_sql_injection_is_data(session: Session) -> None:
    hits = global_search(session, "'; DROP TABLE players;--")
    assert hits == []
    # DB intact — a follow-up query still works.
    assert global_search(session, "McCaffrey")


def test_regex_metachars_literal(session: Session) -> None:
    # No re in the path — metachars match literally (and nothing in the fixture).
    for q in (".*", "(", "[", "a.*b", "^Justin$"):
        assert global_search(session, q) == []


def test_script_tag_is_inert_data(session: Session) -> None:
    # Backend returns the hostile string as plain data (React escapes on render).
    assert global_search(session, "<script>alert(1)</script>") == []


def test_blank_and_whitespace_query_empty(session: Session) -> None:
    assert global_search(session, "") == []
    assert global_search(session, "   ") == []
