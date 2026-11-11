# Plan — Championship flag, playoff/consolation differentiation, Sacko

## Context

Three related honesty/recognition gaps in how the dashboard treats the postseason:

1. **No championship distinction.** A title game (winners'-bracket final) renders with the
   same generic `playoff` badge as a semifinal or a 3rd-place game. The championship deserves
   its own flag that propagates everywhere a playoff flag would appear.
2. **Consolation games masquerade as playoff games.** Several surfaces key off raw
   `Matchup.is_playoff` (a week-boundary flag that is `True` for *every* post-regular-season
   game, including the consolation/"toilet" bracket). So records and rivalries — e.g. the
   Rivalries "hottest rivalries" / playoff-stakes math — count consolation games as true
   playoff meetings. Consolation is **not** a true-playoff achievement and must be
   differentiated. `bracket.py` already reliably separates the championship vs consolation
   halves by matchup connectivity; that derivation is currently trapped inside the one
   `/bracket` endpoint and is not reused.
3. **The Sacko (last place) is unrecognized.** The league brands its last-place team the
   "Sacko". The toilet-bowl final loser is computable from the consolation bracket but is
   surfaced nowhere. It belongs — with a 💩 — on owner pages, team-season headers, the record
   book, and hardware/trophy areas (as the anti-trophy).

**Decisions locked with the user:** Sacko = **toilet-bowl final loser** (derived from the
consolation bracket via `bracket.py`, *not* the stored `Season.last_place_team_id`; that column
is a corroborating cross-check / fallback only). Ship as **one combined feature**.

**Honesty constraint (hard rule):** where the consolation bracket is *not* distinguishable
(`bracket.py`'s `consolation_distinguished == False` — typically older/smaller brackets), we
must NOT fabricate a consolation/championship split or a Sacko. Those stay `playoff`-generic /
`available:false`, never a guessed value. The championship game itself can still be anchored
authoritatively on `Season.champion_team_id` (the final whose winner is the champion).

Git: cut **`feature/championship-consolation-sacko` from `dev`** (current branch is unrelated).

---

## Part A — Shared postseason classifier (the keystone)

Extract `bracket.py`'s component-split logic into a reusable, memoized classifier so every
consumer agrees. New function in `src/ff_dashboard/analytics/bracket.py` (reusing
`_connected_components`, `_order_components`, and the existing game-label derivation):

```
postseason_classification(session, season_id) -> {
    "season_id", "season_year",
    "consolation_distinguished": bool,
    "by_matchup_id": { matchup_id: {
        "tier": "championship" | "playoff" | "consolation",   # None where indistinguishable
        "game_label": str | None,                              # "Championship", "3rd Place", "Toilet Bowl", …
    }},
    "championship_matchup_id": int | None,   # final whose winner == Season.champion_team_id
    "sacko": { "team_id", "owner_id", "matchup_id", "season_year" } | None,   # toilet-bowl final loser
}
```

- **tier:** games in `components[0]` (lowest final ranks) → `playoff`; later components →
  `consolation`. The single `championship` game = the playoff-bracket final whose winner ==
  `Season.champion_team_id` (cross-checked against the connectivity-derived "Championship"
  label; if they disagree, trust `champion_team_id` and downgrade the label tier to `playoff`).
- **sacko:** loser of the consolation final with the numerically-highest place label (the
  "Nth Place" game with largest N → its loser is dead last). `None` when
  `consolation_distinguished` is False. Assert/cross-check against `Season.last_place_team_id`;
  where the bracket can't distinguish but the column exists, expose `sacko` as a **caveated
  fallback** (flagged `source:"recorded"`) rather than a gap, so coverage isn't lost.
- Memoize per `season_id` (module-level `dict` cache keyed by session id + season, mirroring how
  `season_bracket` is already re-invoked by `rivalries._finals_index`).
- Refactor `season_bracket` to consume this so the `/bracket` endpoint and everyone else share
  one source of truth (no behavior change to the bracket view).

Add a `SACKO_GAME_LABEL` / tier label constants alongside the existing `_LABELS`.

---

## Part B — Propagate the three-way classification

**`analytics/head_to_head.py` (`all_pairwise`)** — enrich each meeting dict (and the per-pair
agg) with `bracket_tier`. Replace the blunt `playoff_meetings` counter with a
**non-consolation** count: `is_true_playoff = is_playoff and tier != "consolation"`. Keep raw
`is_playoff` on the meeting for back-compat, add `bracket_tier` + `is_championship`. Build the
classification once per distinct `season_id` seen.

**`analytics/rivalries.py`** — `playoff_rivalries`, `rivalry_intensity` (`_W_STAKES`), and
`rivalry_records` switch their playoff/stakes logic to the **non-consolation** count. Consolation
meetings are surfaced separately/labeled, never folded into "playoff meetings". `_finals_index`
already pulls labels from `bracket.py` — point it at the new classifier and add the toilet-bowl
label so a consolation finals meeting reads as such (not as a blank).

**`analytics/matchups.py`** (`week_matchups`, `box_score`, and the 3rd is the schedule/list at
~L1204) — add `bracket_tier` + `game_label` next to the existing `is_playoff`. 
**`analytics/matchup_flags.py`** — add a `championship` superlative flag (tone `win`/trophy) for
the title game and a `consolation` flag (tone `muted`) so the flag row reflects the tier, keeping
the "all rules backend-side" contract.

**`analytics/owners.py`** — `made_by_season` already excludes consolation via `is_consolation`,
but that column is unpopulated; switch the `is_playoff and not is_consolation` gate to the new
classifier's `tier != "consolation"` so `made_playoffs` stops counting consolation appearances.

---

## Part C — Sacko recording & surfacing

Source: `postseason_classification(...)["sacko"]`. Add a small helper
`season_sacko_map(session) -> {season_id: sacko_dict}` (and an owner→count rollup) in
`owners.py` or a new `analytics/hardware.py`.

- **`analytics/owners.py`** — `_season_result`: return `"Sacko"` when the team is that season's
  sacko. Career dict: add `sackos` count. `trophy_case` build: also include sacko seasons with an
  `is_sacko` flag (so the hardware strip can show the 💩 anti-trophy), not just top-3 finishes.
- **`analytics/teams.py`** — `team_overview` (~L98): add `is_sacko: bool` next to `is_champion`.
- **`analytics/records.py`** — `championships()` per-season `last_place` → add `sacko` (the
  derived toilet-bowl loser) + an `is_distinguished` flag; add a **"most Sackos"** record in the
  records-without-scored-data block (anti-`most_championships`).
- **`analytics/league_history.py`** — per-season already emits `last_place`; add the derived
  `sacko` ref so the league timeline can mark it.

---

## Part D — API schema + client

- Extend `api/schemas.py`: matchup/box-score schemas gain `bracket_tier` + `game_label`;
  rivalry playoff/intensity schemas gain consolation-aware counts; owners career +
  trophy-case + `_season_result`, team overview, and records `championships`/records schemas
  gain `sacko` / `is_sacko` / `sackos`. Update affected route response models in
  `api/routes/{records,seasons,rivalries,...}.py`.
- `cd web && npm run gen:api` then `git diff --exit-code web/src/lib/api` (drift check). **Never
  hand-edit** the generated client.

---

## Part E — Web rendering

- **Distinct badges by tier** wherever the generic playoff badge renders today:
  - `features/matchups/MatchupsPage.tsx` (L68 eyebrow) and `BoxScorePage.tsx` (L311 badge):
    `championship` → trophy/accent badge ("Championship"); `playoff` → existing; `consolation`
    → muted "Consolation" badge.
  - `features/managers/ManagerStory.tsx` (L135) playoff-heartbeat eyebrow respects the tier.
- **Sacko / 💩 hardware:**
  - `design-system/index.tsx`: add a `Sacko` primitive (or a `Trophy` variant) rendering 💩 with
    count, mirroring `Trophy` (L254).
  - `features/managers/ManagerProfilePage.tsx`: season table result cell (L87) shows 💩 for sacko
    seasons; career header + Hardware strip (L262/L267) show a Sacko tally alongside Titles.
  - `features/teams/TeamPage.tsx`: season header shows the 💩 Sacko mark when `is_sacko`.
  - `features/records/RecordsPage.tsx`: render the new "most Sackos" record; championship/dynasty
    timeline shows the per-season Sacko (💩) beside the champion.
  - `features/league/LeagueHistoryPage.tsx` (L435 last_place block): label the derived Sacko with 💩.
- Empty/gap states: where a season's consolation isn't distinguishable, render the existing
  `DataGap` affordance — never a fabricated Sacko or consolation tag.

---

## Tests

- **`tests/dashboard/test_bracket.py`** — `postseason_classification`: a distinguishable season
  (tiers + championship id anchored on champion + sacko = toilet-bowl loser), an
  indistinguishable season (tier None, sacko None or recorded-fallback). Cross-check vs
  `last_place_team_id`.
- **`tests/dashboard/test_head_to_head.py` / `test_rivalries.py`** — `playoff_meetings` excludes a
  seeded consolation meeting; `is_championship` set on the title meeting.
- **`tests/dashboard/test_matchups.py` / `test_matchup_flags.py`** — championship + consolation
  flags/tier emitted on the right games.
- **`tests/dashboard/test_owners.py` / `test_teams.py` / `test_records.py`** — sacko surfaces;
  `made_playoffs` no longer counts consolation; "most Sackos" record.
- **Web**: extend the existing `*.test.tsx` for the new badges and 💩 hardware; update fixtures.

---

## Verification (green gate)

1. Backend: `uv run pytest tests/dashboard -q` (scope to touched files while iterating),
   `uv run ruff check -q && uv run ruff format --check`, `uv run mypy src/ff_dashboard`.
2. Contract: `cd web && npm run gen:api && git diff --exit-code web/src/lib/api`.
3. Frontend: `npm run typecheck && npm run lint && npm run test`.
4. Forbidden-write grep stays clean (read-only; classifier adds no writes).
5. Manual click-through: a known championship game shows the Championship badge; a known
   consolation game shows Consolation (not playoff); Rivalries playoff counts drop where a pair
   only met in consolation; a known Sacko owner/team/season shows 💩 in hardware/records.
6. Update `PROGRESS.md` + `CHANGELOG.md`; commit with `AI-Model`/`Prompted-By`/`Reviewed-By`
   trailers (no `Co-Authored-By`).

## "Done when"

- One shared classifier; no surface reads raw `is_playoff` to mean "true playoff".
- Championship game carries its own flag everywhere a playoff flag would show.
- Consolation games are visibly differentiated and excluded from playoff records/stakes.
- Sacko (toilet-bowl loser) is recorded and surfaced with 💩 on owners/team/records/league/
  hardware, honest (gap or caveated-fallback) where the bracket can't distinguish it.
- Full green gate; manual click-through done.
