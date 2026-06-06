# fix-pass P3 — Search: scope, teams, hardening (PLAN)

Plan for fix-pass **P3** of the 2026-06 review program
(`docs/plans/REVIEW_FIXES_ROADMAP.md`). Findings: **F-44, F-45, F-47**.
Authoritative scope: review doc § "P3 — Search (scope, teams, hardening)".

Layer: data/analytics + api + tests. **No API response-shape change** is required
(F-46 dropdown scroll is frontend and lives in **P5**, not here) — `SearchHit`
already carries `{type, id, label, sublabel, href}`. `gen:api` drift must stay clean.

## Done when (verbatim, sharpened)

> Search returns only league-relevant players; team queries resolve across synonyms
> and surface players-by-team; fantasy team names are searchable; injection/regex
> tests pass; gate green.

Sharpened acceptance:
- A never-rostered "ghost" (e.g. A.J. Feeley) appears **nowhere** in `/v1/search`
  results — search applies the same `team_rosters` scope as `list_player_index`.
- An NFL team query matched by **city, nickname, or abbreviation** (e.g.
  "Minnesota" / "Vikings" / "MIN") surfaces that team's **league-relevant** players.
- A **fantasy team name** (e.g. "Northvale") returns a hit that deep-links to the
  owner who held that team (`/managers/{owner_id}`) — no dead team page.
- Hostile/odd input (SQL LIKE wildcards `%` `_`, `'; DROP`, `<script>`, regex
  metachars `.*`) is treated as **data**: no crash, no over-match, no injection.

## Current state (what's already there)

- `src/ff_dashboard/analytics/search.py:global_search(session, q, limit=10)` —
  ranks owners > seasons > players; prefix(0) over substring(1). Players come from
  the Phase-1 `search_players(session, name=q, limit=limit)`. **Teams are
  deliberately excluded today** (docstring) — P3 reverses that for fantasy teams.
- `src/ff_dashboard/api/routes/search.py` — thin route, `GET /v1/search`.
- Phase-1 `ff_pipeline.repository.queries.search_players(...)` already accepts
  `league_relevant: bool | None` and `nfl_team: str | None` — **F-44 and
  players-by-team need no Phase-1 change** (read-only boundary respected).
- `ff_pipeline.repository.models.Team` has `team_name`, `owner_id`, `season_id`
  (fantasy team names live here, per-season, joined to an owner).
- Existing test `tests/test_p10_search_unit.py::test_teams_are_never_emitted`
  asserts the *old* "no team hits" behaviour — **P3 must update/replace it**.
- Tests are flat under `tests/test_*.py` (not `tests/dashboard/`), per the P2
  layout note — the new suite is `tests/test_search.py`.

## Files to create / touch

| Path | Change |
|------|--------|
| `src/ff_dashboard/analytics/search.py` | F-44 league scope; F-45 NFL-team synonyms + players-by-team + fantasy-team branch; drop the `rank=None→1` coercion (input hardening) |
| `src/ff_dashboard/analytics/nfl_teams.py` *(new)* | static NFL team synonym table: `{city, nickname, abbrev} → abbrev`; `resolve_nfl_team(q) -> str | None` |
| `tests/test_search.py` *(new)* | F-47 functional + security suite (known-answer + edge cases) |
| `tests/test_p10_search_unit.py` | replace `test_teams_are_never_emitted` with the new fantasy-team expectation |
| `tests/conftest.py` | add one distinctive fantasy `team_name` (e.g. "Northvale Scumbags") so fantasy-team search isn't a trivial alias of an owner name; preserve P1's 2015 bracket / 2017 wk4 cap rows |
| `docs/05_API_CONTRACT.md` | `/v1/search` § — document the new match classes (no shape change) |

No route signature change. No schema change. No frontend change in this pass
(F-46 scroll is P5).

## Design / signatures

### F-44 — league-scope the player branch
In `global_search`, call:
```python
search_players(session, name=query, league_relevant=True, limit=limit)
```
Ghosts (`last_rostered_season IS NULL`) drop out — consistent with
`list_player_index`'s default `scope="league"`.

### Input hardening (correctness + F-47)
Currently:
```python
rank = _match_rank(name, query)
if rank is None:
    rank = 1          # <-- keeps non-matching players (over-match on `%`/`_`)
```
Change to **skip** players whose `_match_rank` is `None`. Because Phase-1's
`name.ilike(f"%{name}%")` treats `%`/`_` as LIKE wildcards, a query of `%` pulls
arbitrary players into the candidate pool; re-filtering through `_match_rank`
(plain casefold `startswith`/`in`, no regex) means a wildcard/metachar query
yields only genuine substring hits — wildcards are neutralised dashboard-side
without modifying Phase-1. SQL stays parameterized (no injection); `_match_rank`
uses no `re`, so regex metachars are literal.

### F-45 — NFL team synonyms + players-by-team
New `analytics/nfl_teams.py`:
```python
def resolve_nfl_team(q: str) -> str | None:
    """Case-insensitive map of an NFL city/nickname/abbrev to its team abbrev.

    "minnesota" | "vikings" | "min"  -> "MIN".  None if no synonym matches.
    Abbrevs match the values stored in Player.nfl_team.
    """
```
Backed by a static table of all 32 teams keyed on casefolded
city / nickname / abbreviation. (Handle multi-team cities — "new york" →
both NYG/NYJ; "los angeles" → LAR/LAC — by allowing the resolver to return a
short list, or model it as `resolve_nfl_teams(q) -> list[str]`.) **Decision to
confirm in BUILD:** singular vs. list return — see Open questions.

In `global_search`, when `resolve_nfl_team(query)` hits, also pull
`search_players(session, nfl_team=abbrev, league_relevant=True, limit=limit)`
and emit those as `type="player"` hits (deduped by `player_id` against the
name-branch results). NFL teams themselves get **no** standalone hit (no NFL-team
page) — the synonym is a query expander into players-by-team.

### F-45 — fantasy team names
New branch over `Team` (join `Team.owner`), matching `Team.team_name` with
`_match_rank`. Emit:
```python
{
  "type": "team",
  "id": <owner_id>,            # resolve to the owner (no team page)
  "label": team_name,
  "sublabel": f"Fantasy team · {year}",   # or "Manager: {display_name}"
  "href": f"/managers/{owner_id}",
}
```
A team name reused across seasons/owners: collapse to the **most recent**
season's owner (single hit per distinct `team_name`). Insert in the type-rank
order between owner and season (proposed `_TYPE_RANK`: owner 0, team 1,
season 2, player 3) so the most navigationally useful hits stay on top.

## Test list (`tests/test_search.py` + conftest)

**F-44 scope**
- `test_search_excludes_never_rostered` — add a ghost player (no `team_rosters`
  row, `last_rostered_season=None`) to the fixture named to match a query; assert
  no player hit for it; assert a rostered player with the same substring *is*
  returned. (Mirrors the index `scope=league` invariant — gap case.)

**F-45 NFL team / players-by-team** (fixture: jjet=MIN, lamar/dst=BAL, cmc=SF, kelce=KC)
- `test_nfl_team_by_nickname` — "Vikings" → Justin Jefferson among hits.
- `test_nfl_team_by_city` — "Minnesota" → Justin Jefferson.
- `test_nfl_team_by_abbrev` — "MIN" → Justin Jefferson.
- `test_nfl_team_players_are_league_scoped` — an unrostered MIN player is excluded.
- `test_unknown_team_token_no_crash` — "Atlantis" resolves to no team, returns
  normal name-matched hits only.

**F-45 fantasy team names**
- `test_fantasy_team_name_match` — "Northvale" → a `type="team"` hit href
  `/managers/{owner_id}` for the owner who held it.
- `test_fantasy_team_dedup_recent_owner` — a name reused across seasons yields one
  hit pointing at the most-recent owner.
- Replace `test_teams_are_never_emitted` accordingly (team hits are now expected
  for fantasy names; still no NFL-team standalone hit).

**F-47 security / hardening**
- `test_like_wildcards_are_literal` — `%`, `_`, `%a%` return only genuine
  substring matches (no full-table dump).
- `test_sql_injection_is_data` — `"'; DROP TABLE players;--"` returns `[]`/sane
  hits, raises nothing, DB intact (read-only anyway).
- `test_regex_metachars_literal` — `".*"`, `"("`, `"["` don't error and match
  literally (no `re` in the path).
- `test_script_tag_is_inert_data` — `"<script>alert(1)</script>"` returns `[]`,
  no error (XSS is a render concern; backend treats it as plain text — frontend
  escaping noted below).
- `test_blank_and_whitespace_query_empty` — `""`, `"   "` → `[]` (route already
  enforces `min_length=1`; analytics returns `[]` for stripped-empty).

Keep using `tests/conftest.py::KNOWN` for ids. Coverage must not regress.

## Frontend note (F-47 XSS, no code change expected here)

The SPA renders search labels via React, which escapes text by default, so a
`<script>` label is inert. P3 adds a backend test asserting the API returns the
hostile string as inert data; if BUILD finds any `dangerouslySetInnerHTML` on the
search dropdown it becomes a P5 item (log it), **not** a P3 change. F-46 (scroll)
is already P5.

## Open questions (resolve in BUILD, default if unanswered)

1. **Multi-team cities** ("New York", "Los Angeles"): return a list of abbrevs vs.
   first match. **Default:** `resolve_nfl_teams -> list[str]`, emit players for all
   matched teams (the review explicitly flags "New York" → only Giants as wrong).
2. **NFL-team standalone hit:** none (no team page) — synonym only expands to
   players. **Default:** as stated; revisit only if a team landing view appears.
3. **Fantasy-team sublabel wording:** "Fantasy team · {year}" vs.
   "Manager: {name}". **Default:** "Fantasy team · {year}". Reuse existing copy
   conventions if one exists.

## Considerations to surface (append to roadmap on BUILD)

- Phase-1 `search_players` ilike treats `%`/`_` as wildcards; P3 neutralises this
  dashboard-side (re-filter via `_match_rank`) rather than touching Phase-1
  (read-only boundary). → no Phase-1 change.
- F-45 needs a distinctive fantasy `team_name` in the fixture (today
  `team_name = f"{display_name} {year}"`, an owner-name alias) → conftest gains one
  "Northvale Scumbags"-style team; preserve P1's 2015 bracket + 2017 wk4 cap rows.

## Not in scope

F-46 (dropdown scroll, frontend) → **P5**. Any pre-2016 scoring reconstruction,
ownership succession, or NFL.com scrape → **UP**. No new endpoints; no response
shape change.
