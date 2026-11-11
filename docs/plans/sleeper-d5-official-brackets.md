# Plan — Sleeper D5: official brackets, divisions, potential points

Branch: `feature/sleeper-d5-official-brackets` (from `dev` @ 1905eb0, after D4 merged as PR #131).
Sources: `docs/sleeper/00_UPSTREAM_STATE.md` §3/§4/§6, `docs/sleeper/02` D5, `01` §3 rows 61/62/101/106/107.

**Done when (verbatim):** 2026 playoffs render from official brackets; legacy brackets look identical
to today with a "derived" provenance note; Sacko derivation agrees on both.

## What exists today (probed 2026-11-10)

- `analytics/bracket.py`: `season_bracket` (route `GET /v1/seasons/{id}/bracket`, schema
  `SeasonBracket`) and `postseason_classification` (the shared championship/playoff/consolation tiers
  + Sacko, used by records, stories and `season_sacko_map`). Both derive the bracket from matchup
  connectivity. Hotspot `00` §6: for Sleeper seasons, prefer `queries.brackets_for_season`.
- `playoff_brackets` rows: `bracket` (`winners`/`losers`), `round`, `match_no`, `team1_id`,
  `team2_id`, `winner_team_id`, `loser_team_id`, `placement` (Sleeper `p`), `team1_from` /
  `team2_from` (`{"w": m}` / `{"l": m}`), `source`. No scores. Pre-generated with current seeds before
  week 15, so in-season 2026 has seeded pairings with no winners.
- Computed potential points already exist: `analytics/efficiency.py` sums the box score's
  `optimal_total` per team-week (the canonical optimal-lineup solver). Nothing exposes it as
  "potential points", and Sleeper's official `teams.extra_data.ppts` is unused.
- Divisions: standings rows carry `conference_id` / `conference_name` (derived, 2010–2019 via
  `historical_divisions` + `conferences`). 2026 `teams.division` is NULL and `official_divisions` is
  `not_used`, which renders nothing.
- Legacy parity is a **subset** check (`subset_diffs`: new keys allowed, existing values must hold).
  So every D5 addition can be additive with no golden regeneration. Required: no existing legacy value
  moves.
- The mixed fixture stops at week 9, so its brackets are seeds only. A decided bracket needs a fixture
  variant (upstream `test_sleeper_rich._decided`: weeks 6–8 become the playoffs, and the higher real
  score wins each game).

## Decisions taken in this plan (flag at PR; no new user question)

1. **Extend `/v1/seasons/{id}/bracket` additively instead of adding `/brackets`.** `02`/`01` name a
   new `/brackets` route that "falls back to today's derived shape" for legacy. One route with the same
   shape plus `source` does the same with no duplicate endpoint, and the subset parity allows it.
   Recorded as a deviation.
2. **Potential points: one method across eras** (`01` row 101 wins over row 61). `potential_points` is
   always the BFF-computed optimal total. Sleeper's `ppts` is a separate `potential_points_official`
   cross-check field and is never mixed into the computed series.
3. **The official Sacko** = `seasons.last_place_team_id` on a Sleeper season. Upstream writes it
   from the bracket: `placement` is bracket-relative (Sleeper `p`), and absolute place =
   offset + p for the winner and offset + p + 1 for the loser (losers offset = winners size). It is
   written only once that week is finalized. The Toilet Bowl is the losers game with the highest
   `placement` (11th/12th in a 6+6 league), and its loser must equal `last_place_team_id`. The Sacko is
   never derived for an undecided bracket.

## Scope

### BFF

- **`analytics/brackets.py` (NEW)**
  - `official_bracket(session, season_id) -> dict | None`: maps `brackets_for_season` rows to the
    existing `SeasonBracket` shape (`playoff_bracket` = winners, `consolation_bracket` = losers,
    `consolation_distinguished=True`). It returns `None` when the season has no rows, which means the
    caller falls back.
    - Round labels use the existing `_build_bracket_section` vocabulary.
    - Game labels come from the absolute place (offset + `placement`): 1 = Championship, 3/5 =
      3rd/5th Place, 7/9/11 = 7th/9th/11th Place (the legacy `_LABELS` vocabulary). The top-placement
      losers game is the Toilet Bowl.
    - Byes are teams that first appear in round 2 (`team*_from` null), shown as `bye_teams`.
    - Scores are joined from `matchups` at week `regular_season_weeks + round` for the team pair. The
      join goes through `game_state`, so a pending week gives `score None` and `week_pending True`,
      never a winner (`00` §3).
  - `official_sacko(session, season_id) -> dict | None`: rule 3 above, with
    `{team_id, matchup_id | None, source: "official"}`.
  - `season_brackets(session, season_id)`: official when the `brackets` capability is `available`
    and rows exist. Otherwise it returns `bracket.season_bracket(...)` with `source="derived"`.
- **`analytics/bracket.py`**
  - `postseason_classification` uses the official tiers for a Sleeper season with bracket rows: it
    classifies each played postseason matchup by its bracket game, and the Sacko comes from
    `official_sacko`. The legacy path is unchanged.
  - Idle postseason rows (`postseason_role` `bye`/`placed`, opponent NULL) are never games (hotspot
    §6). Verify `season_bracket`'s connectivity already skips them, and add the guard if it doesn't.
- **`analytics/efficiency.py` → potential points**
  - `season_potential_points(session, season_id) -> dict[int, PotentialPoints]`, keyed by team_id:
    `{computed, official, weeks_counted, partial_note}`. `computed` is the regular-season optimal sum,
    reused from the efficiency loop; extract a shared per-team-week helper so it isn't re-solved.
    `official` comes from `teams.extra_data.ppts` (`None` on legacy).
  - Unfinished weeks are excluded (D3 rule). Regular-season scope is the same window as PF.
  - **`bench_or_reserve` weeks** (2026 weeks 1–8: IR players sit in `BN`) let the solver start an IR
    player, so `computed` can exceed Sleeper's `ppts`. The function gets a `partial_note` naming those
    weeks, and the two values are never reconciled by hand.
  - A team-week with no roster rows is a gap: `computed None`, never 0.
- **Standings payload** (route-level, not `compute_standings`, so the many standings consumers don't
  pay for the solver)
  - Adds `potential_points`, `potential_points_official` and `potential_points_note` to each
    `StandingRow`, plus `division_source: "official" | "derived" | None` next to `conference_*`.
  - Official divisions: a Sleeper season whose `teams.division` is set, with the capability
    `available`, uses it as the `conference_*` values with `division_source="official"`. When the
    capability is `not_used`, the fields stay None and nothing renders.
- **Schemas (`api/schemas.py`), all additive / optional**
  - `SeasonBracket`: `source: Literal["official","derived"] = "derived"`, `provenance_note: str`,
    `is_provisional: bool = False` (an active season whose bracket is undecided).
  - `BracketGame`: `matchup_id: int | None` (official games not yet played have no matchup),
    `placement: int | None`, `week_pending: bool = False`.
  - `StandingRow`: the four fields above.
  - Run `npm run gen:api` after the schema change. Don't hand-edit the client.

### SPA (presentation only; copy in `lib/platform.ts`)

- `features/playoffs/PlayoffsPage.tsx`:
  - a `ProvenanceNote` under the bracket from `provenance_note` ("Official Sleeper bracket" /
    "Derived from who played whom", the copy lives in `platform.ts`);
  - placement labels from `game_label`, a pending game as "Awaiting final", and a provisional bracket
    marked "Seeds as of week N — subject to change" (the §3 current-state rule);
  - the Sacko badge is unchanged, since it reads `is_sacko`.
- `features/standings/StandingsPage.tsx`:
  - a "Potential" column (`potential_points`, `DataGap` when null), with the official value as a
    cross-check tooltip/sub-line when present;
  - a `ProvenanceNote` when `potential_points_note` is set;
  - division labels follow `division_source` (no new label when null).

## Tests

**Fixture:** add `decided_mixed_db_path` / `decided_client` to `tests/sleeper_fixture.py`. It
replicates upstream's `_decided` overlay (`playoff_week_start=6`, seeded 6+6 brackets, higher real
score wins) through the packaged loader. Tests may use pipeline loaders (`00` §7).

**Unit (`tests/test_d5_brackets.py`):**
- the official bracket on the decided fixture: 2 sections, labels per placement, byes = seeds 1–2,
  scores joined, champion = `seasons.champion_team_id`;
- the official bracket on the week-9 fixture (undecided): seeded pairings, no winners,
  `is_provisional`, no Sacko;
- **Sacko agreement**: on the decided fixture, `official_sacko` == the connectivity-derived Sacko from
  the same matchup rows == `seasons.last_place_team_id`. On the legacy fixture,
  `postseason_classification` is unchanged (golden) and `source` is `derived`;
- a pending postseason week: `score None`, `week_pending`, no winner;
- idle bye/placed rows are never bracket games and never classified;
- potential points:
  - computed == the efficiency optimal sum (legacy known answer);
  - `official` from `ppts` on Sleeper and None on legacy;
  - the pending week is excluded (rewrite week-9 live scores and get the same output);
  - `bench_or_reserve` weeks give `partial_note`;
  - an empty team-week is None, not 0;
- divisions: `not_used` gives `division_source None` and no conference on 2026 rows. Setting
  `teams.division` on a fixture copy gives `"official"`. Legacy stays `"derived"` where it was set.

**Contract:** `/bracket` and standings goldens on the legacy fixture still pass (subset).
`DZ_UPDATE_GOLDEN=new` adds the 2026 bracket route on the mixed + decided fixtures. The live golden
stays 1092/0. Both parity suites must be green with no regeneration.

**Component:** `PlayoffsPage.test.tsx` covers the official vs derived note, placement labels, the
provisional banner and an awaiting-final game. `StandingsPage.test.tsx` covers the Potential column,
the gap and the cross-check.

**e2e:** extend `e2e/sleeper.spec.ts`: open the Playoffs page for 2026 and see the official note +
seeds/provisional (mixed fixture). The legacy Playoffs visual baseline should not change except for
the note line. If it changes beyond that, stop and inspect.

## Files to touch

`src/ff_dashboard/analytics/{brackets.py (new), bracket.py, efficiency.py}`,
`src/ff_dashboard/api/{schemas.py, routes/seasons.py, routes/<standings route>}`,
`web/src/lib/platform.ts`, `web/src/features/{playoffs,standings}/*`, `web/src/lib/api/` (generated),
`tests/sleeper_fixture.py`, `tests/test_d5_brackets.py`, `e2e/sleeper.spec.ts`, `PROGRESS.md`.

## Risks / watch

- The seeded bracket changes every week until week 15, so treat it as current state, never history.
- Upstream withholds places if the bracket looks loser-advances. In that case `placement`/winner are
  null: render seeds and give no Sacko.
- Efficiency may already re-solve per call, so check the standings route's latency on the live DB
  (16 seasons × 12 teams × 14 weeks). Cache per season if it's slow.

## As built (2026-11-10)

- **Fixture:** `decided_db_path` / `decided_client` (`DecidedSource` in `tests/sleeper_fixture.py`).
  Beyond upstream's `_decided`, it pairs playoff weeks by bracket game (idle teams get no
  `matchup_id`, like real Sleeper) and drops week 9 (a season has no games after its final). Upstream
  places teams 1–12 on it: champion 21, Sacko 27.
- **The derived rule misreads Sleeper.** On the decided fixture it found Sacko 20 (the 9th-place loser),
  not 27, because Sleeper plays the 11th/12th and 5th/6th games a round early. It also rendered
  bye/placed rows as opponent-less games. Fixes:
  - `postseason_classification` uses `brackets.official_classification` for any season with bracket
    rows;
  - `season_bracket` skips idle rows (legacy has none).
- **Sacko:** `source: "official"` = `seasons.last_place_team_id`, tied to the top-placement losers
  game. The test checks it against the fixture's own bracket answer, the recorded value,
  `season_sacko_map` and the bracket flag.
- **Deviation: no `provenance_note` field.** `source` + `is_provisional` carry it, and the copy is in
  `lib/platform.ts` (`bracketProvenanceText`, `PROVISIONAL_BRACKET_TEXT`).
- **Potential points:**
  - Implemented as `efficiency.season_potential_points` on a shared `team_lineup_weeks`. Standings rows
    get `potential_points` / `potential_points_official`, and the payload gets
    `potential_points_uncertain_weeks` (it's a week list, not prose, so the SPA writes the note).
  - Cached per (season, through_week, pipeline run). Live 2024: 2.3 s cold, 7 ms warm.
  - On the mixed fixture, computed == Sleeper `ppts` for every team despite weeks 1–8 being
    `bench_or_reserve`.
- **Leak fixed:** `season_efficiency` counted the unfinished week's live player points (it never
  checked pending). It now skips pending team-weeks. This changes 2026 only.
- **Divisions:**
  - `conferences.official_division_map` feeds `compute_standings` rows and `conference_map` when
    `teams.division` is set;
  - Standings gets `division_source` (`official` / `derived` / null);
  - `not_used` renders nothing.
- **Open (not D5 "Done when"):**
  - the 2010–2019 divisions view (`/conferences`) has no Potential column and no official-division
    path;
  - Playoffs has no visual baseline (add in D8 per-era baselines).
- **Gate:**
  - pytest 586 passed / 1 skipped, ruff + mypy clean, write-check empty;
  - contract no drift, Prettier + tsc clean, vitest 239, e2e 19/19;
  - both parity suites + live golden green with no regeneration;
  - live click-through of 2025 Playoffs / Standings done.
