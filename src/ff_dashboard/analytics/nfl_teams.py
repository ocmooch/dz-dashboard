"""Static NFL city/nickname/abbreviation synonyms for search expansion.

Maps a free-text NFL team token (city, nickname, or abbreviation, any case) to
the team abbreviation(s) stored in ``Player.nfl_team``. Global search uses this
to expand a team query into that team's league-relevant players — there is no
standalone NFL-team page, so this is a query *expander*, not a hit type.

Multi-team metros ("new york", "los angeles") resolve to *both* franchises; the
resolver returns a list so the caller can union their players. Historical/alt
abbreviations (e.g. "oak"/"sd"/"stl") fold to the current franchise code so an
old query still resolves; the value the player actually carries in
``Player.nfl_team`` is whatever nflverse ships (current), so a returned abbrev is
matched exactly against that column by the caller.
"""

from __future__ import annotations

# (current abbrev, city, nickname, *extra tokens incl. historical/alt abbrevs).
# Tokens are matched case-insensitively as whole strings (no substring/regex).
_TEAMS: tuple[tuple[str, ...], ...] = (
    ("ARI", "arizona", "cardinals", "cards"),
    ("ATL", "atlanta", "falcons"),
    ("BAL", "baltimore", "ravens"),
    ("BUF", "buffalo", "bills"),
    ("CAR", "carolina", "panthers"),
    ("CHI", "chicago", "bears"),
    ("CIN", "cincinnati", "bengals"),
    ("CLE", "cleveland", "browns"),
    ("DAL", "dallas", "cowboys"),
    ("DEN", "denver", "broncos"),
    ("DET", "detroit", "lions"),
    ("GB", "green bay", "packers", "gnb"),
    ("HOU", "houston", "texans"),
    ("IND", "indianapolis", "colts"),
    ("JAX", "jacksonville", "jaguars", "jags", "jac"),
    ("KC", "kansas city", "chiefs", "kan"),
    ("LAC", "los angeles", "chargers", "san diego", "sd", "sdg"),
    ("LAR", "los angeles", "rams", "st louis", "st. louis", "stl", "la"),
    ("LV", "las vegas", "raiders", "oakland", "oak", "lvr"),
    ("MIA", "miami", "dolphins"),
    ("MIN", "minnesota", "vikings", "vikes"),
    ("NE", "new england", "patriots", "pats", "nwe"),
    ("NO", "new orleans", "saints", "nor"),
    ("NYG", "new york", "giants"),
    ("NYJ", "new york", "jets"),
    ("PHI", "philadelphia", "eagles"),
    ("PIT", "pittsburgh", "steelers"),
    ("SEA", "seattle", "seahawks"),
    ("SF", "san francisco", "49ers", "niners", "9ers", "sfo"),
    ("TB", "tampa bay", "buccaneers", "bucs", "tam"),
    ("TEN", "tennessee", "titans"),
    ("WAS", "washington", "commanders", "redskins", "football team", "wsh", "was"),
)


def _build() -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for abbrev, *tokens in _TEAMS:
        for tok in (abbrev.casefold(), *(t.casefold() for t in tokens)):
            bucket = table.setdefault(tok, [])
            if abbrev not in bucket:
                bucket.append(abbrev)
    return table


_SYNONYMS = _build()


def resolve_nfl_teams(q: str) -> list[str]:
    """Resolve an NFL city/nickname/abbreviation token to team abbreviation(s).

    Case-insensitive, whole-token match (no substring or regex semantics):
    ``"vikings" | "minnesota" | "min" -> ["MIN"]``; ``"new york" -> ["NYG", "NYJ"]``.
    Returns ``[]`` when nothing matches. The returned abbreviations are those
    stored in ``Player.nfl_team``.
    """
    return list(_SYNONYMS.get(q.strip().casefold(), []))
