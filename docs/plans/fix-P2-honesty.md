# fix-pass P2 — Data honesty & affordance precision (+ gap-validation harness)

Plan doc for fix-pass **P2** of the 2026-06 review-fixes program
(`docs/plans/REVIEW_FIXES_ROADMAP.md`). Findings: **F-16, F-35, F-26, F-33, F-48, F-43**
(review doc § "P2 — Data honesty & affordance precision"). Base: `dev` (after PR #30 / P1 merged).
Branch: `feature/fix-P2-honesty` → PR to `dev`.

## Done when (verbatim from review, sharpened)

> No view labels complete 2010–2015 team/roster data as incomplete; one warm, consistent
> pre-2016 affordance; harness asserts the coverage truths and is green; gate green.

Sharpened: every pre-2016 affordance scopes the gap to **per-player fantasy scoring** and
affirms that **team results, standings, rosters, and drafts are complete** for 2010–2015; a
pre-2016-only rostered player (Hernandez) reads as a real league player from the unscored era,
not as empty/error; the new harness asserts the coverage truths and would mechanically have
caught F-16/F-22/F-25/F-31/F-35.

## Guiding insight (from BUILD-recon — keeps the pass small & contract-safe)

The affordance **mechanism** (keying off season-level `is_scored`) can stay. The defect is one
of **copy precision and consistency**, plus one missing player-detail affordance. The data the
copy needs is already in the responses (`is_scored`, `first/last_rostered_season`, coverage
`scored_year_min`). So:

- **No API response-shape change.** Keep `is_scored` and `dst_scoring_complete` as-is →
  `gen:api` drift stays clean. F-48 is a *documentation + flag-meaning* reconcile, not a shape
  change.
- All math/derivation stays backend; the frontend only re-words and re-composes existing flags.
- One shared copy string for the pre-2016 gap (F-33), reused across matchups/teams/stats/players.

## Files to create / touch

### Frontend (copy precision + the one shared affordance)
- `web/src/design-system/index.tsx` — `DataGap` reason map:
  - Reword `season_unscored` → scopes to player scoring, affirms team data complete.
  - Add reason `pre2016_unscored_rostered` (F-26): "Rostered in the unscored era (2010–2015) —
    per-player fantasy scoring not reconstructed; team results & rosters are complete."
  - Export a shared `PRE2016_GAP_NOTE` constant so banners and gaps read identically (F-33).
- `web/src/features/matchups/MatchupsPage.tsx:108` (**F-16**) — banner: affirm team results +
  margins are complete for 2010–2015; scope the gap to per-player box scores. Keep gating on
  `!data.is_scored`.
- `web/src/features/teams/TeamPage.tsx:134` & `:309` (**F-35**) — roster-points cell + summary
  banner copy: the *points* are unavailable (player scoring), the roster itself is complete; no
  wording that implies the roster/week is unscored.
- `web/src/features/stats/StatsPage.tsx:82` (**F-33**) — unify pre-2016 copy to the shared note.
- `web/src/features/players/PlayerDetailPage.tsx:78-86` (**F-26**) — when the player's rostered
  span is entirely pre-`scored_year_min` (≤2015), render the `pre2016_unscored_rostered`
  affordance instead of the bare "No scored data" / "No scored weeks".
- `web/src/app/shell/AppShell.tsx:38` — selector "· not scored" label: align wording (minor;
  keep compact).

### Backend (harness + flag reconcile — no shape change)
- `tests/test_coverage_integrity.py` (**NEW, F-43**) — the gap-validation harness. (Path note:
  the repo's tests live flat under `tests/test_*.py`, not `tests/dashboard/` as CLAUDE.md's
  command examples imply; follow the actual layout.)
- `src/ff_dashboard/analytics/coverage.py` (**F-48**) — tighten the `dst_scoring_complete`
  docstring to state precisely what it asserts (every scored season carries ≥1 scored DEF row =
  "DST is scored") and that the *known DST yards/sacks accuracy* concern is a separate upstream
  data-quality gap, **not** a presence gap → flag stays `True` honestly. No code/shape change
  unless a real presence gap is found on the fixture.

### Docs
- `docs/03_DATA_ACCESS.md` — record (a) that `is_scored` means *per-player fantasy scoring only*
  (team totals/standings/rosters/drafts are complete 2010–2025) and (b) a dev-facing note on the
  DST yards/sacks upstream gap (F-48). Keep end-user copy unchanged.

## F-43 harness — known-answer tests (read-only, against the conftest fixture)

Module `tests/test_coverage_integrity.py`, using the existing `session` fixture. Assert
**invariants/relationships** (robust to the synthetic fixture years 2015/2016/2017), each a
coverage truth a prior finding violated:

| Test | Asserts | Catches |
|------|---------|---------|
| `test_player_scoring_absent_pre_2016` | `seasons_scored(session)` has no year < 2016; ⊆ `seasons_present` | F-16/F-31 over-claim |
| `test_team_totals_present_unscored_era` | every unscored present-season (e.g. 2015) still has matchup rows with non-null team scores / standings | F-16/F-35 (team data complete) |
| `test_index_has_no_never_rostered` | `list_player_index(scope="league")` rows all have `last_rostered_season is not None` | F-25/F-44 ghosts |
| `test_records_window_matches_coverage` | records team-window spans all team-totals seasons; player-record window ⊆ scored seasons | F-22 |
| `test_dst_flag_consistent_with_def_rows` | `dst_scoring_complete(session)` ⇔ `set(seasons_scored) <= set(seasons_with_dst_scored)` | F-48 flag accuracy |
| `test_coverage_payload_shape` | `compute_coverage` returns the documented keys with correct types | regression net |

Gap case baked in: `test_team_totals_present_unscored_era` is the explicit "complete data in an
unscored season" case (the exact F-16/F-35 scenario) — proves the harness distinguishes
*present team data* from *absent player scoring*.

## Tests to extend (frontend)
- `web/src/features/matchups/matchups.test.tsx` — pre-2016 banner asserts the new precise copy.
- `web/src/features/teams/team.test.tsx` — roster-cell/summary copy.
- `web/src/features/stats/stats.test.tsx` — unified pre-2016 copy.
- `web/src/features/players/players.test.tsx` — pre-2016-only rostered player renders the
  `pre2016_unscored_rostered` affordance, not "No scored data".

## Out of scope (record, don't absorb)
- F-27 pre-2016 scoring **reconstruction** is UP (Phase-1 program), not P2. P2 only makes the
  *current* gap honest.
- F-36 (pre-2016 matchup deep-link broken) and F-34 (team season selector) are **P5**
  navigation/presentation, not P2.
- No `is_scored` / `dst_scoring_complete` shape change; if a real DST presence gap surfaces on
  the real DB it becomes a new finding, not silently flipped here.

## Considerations to surface (append to roadmap log on BUILD)
- The affordance mechanism stays (keying on `is_scored`); P2 is copy-precision + one new
  player-detail affordance + the harness + a docstring/doc reconcile — **no contract change**.
- Tests live flat under `tests/`, not `tests/dashboard/` (CLAUDE.md command path is illustrative).
