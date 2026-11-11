# P — Draft ADP market axis (reach / value, multi-source blend)

Add **Average Draft Position (ADP)** as a second, orthogonal axis on the draft surfaces.
The dashboard already scores the **outcome axis** (did a pick pan out? `value` = points
over slot, and the composite `impact`). This adds the **market axis**: where *this league*
drafted a player vs where the *consensus market* did. Drafted earlier than ADP = a
**reach**; later = a **value/bargain**. The two axes together (reach-that-busted vs
late-gem) are the rich part, and the per-manager aggregate of the market axis is what
exposes drafting *tendencies / strengths / weaknesses*.

Cross-repo, mirroring the roadmap's two-phase shape:
**Phase 1 (danger-zone / ff-pipeline)** ingests + stores ADP; **Phase 2 (dz-dashboard)**
blends, scores, and renders it. The dashboard stays read-only over the Phase 1 DB.

## Session model

`PLAN → BUILD → VERIFY`, and because it is cross-repo, **Phase 1 lands before Phase 2
starts** (the dashboard can't read a table that doesn't exist).

- **PLAN: this document only.** No implementation in this thread.
- **BUILD (Phase 1, danger-zone):** FFC/MFL/Sleeper ADP clients + a shared runner, the
  `player_adp` table + alembic migration, identity matching, `pipeline_runs`/`source_health`
  bookkeeping + a coverage probe, and a read-only `queries.py` helper. Backfill 2010–2025.
- **BUILD (Phase 2, dz-dashboard):** `analytics/adp.py` (the weighted blend + delta), draft
  analytics wiring, `draft_tendencies()`, API schema fields + `gen:api`, and the four UI
  surfaces.
- **VERIFY:** Phase 1 gate (pytest + ruff + mypy) + a real-DB backfill spot-check; Phase 2
  full dashboard green gate + `gen:api` drift + manual click-through of a known draft
  (2015) confirming reach/value chips, the quadrant, and a team's tendencies card.

Read narrowly per the token budget. Phase 1: the Sleeper crawler (`crawlers/sleeper/`),
`repository/models.py` (table patterns), `normalizer/player_ids.py` (the resolver),
`alembic/`. Phase 2: existing `analytics/draft.py`, the Draft rows of
`05_API_CONTRACT.md` / `07_PAGES_AND_VIEWS.md`, `08_TESTING_STRATEGY.md` draft lines,
`DraftPage.tsx`. **Do not open generated/lock/`schema.d.ts` files.**

## Decisions locked (from kickoff)

- **Sources: blend FFC + MFL + Sleeper**, FFC weighted primary (most robust + team-count
  aware), MFL trusted secondary (known profile), Sleeper modern-only (≈2018+, empty before).
  Store **raw per-source rows**; compute the weighted composite **in dashboard analytics**
  (tunable knobs, not baked into storage). Cross-source disagreement is itself a signal.
- **Format per season: fixed map.** 2010 = **half-PPR**; 2011–2025 = **full-PPR**.
  Fallback chain **full-PPR → half-PPR → standard (0-PPR, emergency only)**. Every
  non-primary format is **recorded on the row and surfaced loudly** — never a silent
  substitution.
- **Build all four UI surfaces** (chip, reaches/values leaderboards, reach×outcome
  quadrant, manager tendencies), each behind a small toggle/flag so any can be hidden or
  retired later without unwinding the others.

## Concept & conventions (lock the signs once)

Both axes are per pick, **independent**, and either may be unavailable:

| | Market axis (NEW) | Outcome axis (exists) |
|---|---|---|
| Source | external ADP vs our `overall` | `season_points` vs slot expectation |
| Number | `adp_delta` | `value` / `impact` |
| Available when | player has a blended ADP | player has a scored total (or genuine 0) |

- `adp_delta = round(overall − composite_adp, 1)`.
  **Positive ⇒ drafted *later* than market (`overall` is a higher pick number than ADP) ⇒
  value/bargain. Negative ⇒ drafted *earlier* ⇒ reach.** Name it explicitly everywhere;
  the sign is the #1 footgun.
- `market_label ∈ {"value", "reach", "on_market"}` (a small dead-band, e.g. |delta| < 1
  round-trip, reads "on market").
- ADP availability is a **separate** sub-state from scoring availability: `adp_available`
  + `adp_reason` (`no_market_data` / `outside_adp_range` / `adp_not_captured`). A pick can
  have an ADP but no score, or a score but no ADP.

---

## Phase 1 — danger-zone (ingest + store)

Mirror `crawlers/sleeper/runner.py` end to end: pull → resolve to our `player_id` → upsert
→ `pipeline_runs` / `source_health` + `unresolved_*` counts. **No writes outside the new
table; no player-stub creation** (skip/park unresolved, per the Sleeper memo).

### 1. New `player_adp` table (additive alembic migration)

Store source-faithful raw rows; blending stays in the dashboard.

```
player_adp(
  adp_id            INTEGER PK,
  season_id         INTEGER FK seasons NOT NULL,
  player_id         INTEGER FK players NULL,   -- resolved canonical; NULL = unmatched,
                                               --   kept for re-match + coverage audit
  source            TEXT NOT NULL,             -- 'ffc' | 'mfl' | 'sleeper'
  source_player_key TEXT,                      -- source id (mfl_id/sleeper_id) or name|team|pos
  source_player_name TEXT,
  source_position   TEXT,
  source_nfl_team   TEXT,
  requested_format  TEXT NOT NULL,             -- league map: 'full_ppr' / 'half_ppr'
  actual_format     TEXT NOT NULL,             -- what was actually available
  format_fallback   BOOLEAN NOT NULL,          -- actual != requested (surfaced, not silent)
  teams             INTEGER,                    -- 12
  adp               REAL NOT NULL,
  adp_stdev         REAL, adp_high REAL, adp_low REAL,
  times_drafted     INTEGER,
  pulled_at         DATETIME, run_id INTEGER FK pipeline_runs,
  UNIQUE(season_id, source, source_player_key)
)
```

Historical ADP is immutable → safe to cache pulls permanently and re-ingest idempotently.

### 2. Source clients (`crawlers/ffc/`, `crawlers/mfl/`, reuse `crawlers/sleeper/`)

Each follows the `LiveSource` + replayable-fixture (respx) split already used.

- **FFC** — `GET https://fantasyfootballcalculator.com/api/v1/adp/{format}?teams=12&year=YYYY`
  (`format ∈ standard|ppr|half-ppr`). Returns name/position/team/adp/stdev/high/low/
  times_drafted. No stable IDs → name+team+pos match. Daily-updated; throttle, attribute,
  cache. ([API](https://help.fantasyfootballcalculator.com/article/42-adp-rest-api))
- **MFL** — `export?TYPE=adp&YEAR=YYYY&...` with format/team-count filters. Gives `mfl_id`.
- **Sleeper** — reuse existing client/ID map; ADP only ≈2018+, **absent earlier (expected,
  not an error)** — record the empty pull in `source_health`.

### 3. Format selection + loud fallback

`requested_format = half_ppr if season.year == 2010 else full_ppr`. Per source, probe
availability for the requested format/year; on miss, walk full→half→standard, set
`actual_format` + `format_fallback=True`, and **emit a WARN + a `source_health` note** so a
substitution is never quiet. (Expect 2010 to be thin — possibly FFC-only and possibly only
standard available; that surfaces here rather than hiding.)

### 4. Identity matching

- **MFL / Sleeper:** map `mfl_id` / `sleeper_id` → our `player_id` via existing id columns
  (`players.sleeper_id`) and/or DynastyProcess `db_playerids` (nflreadpy `load_ff_playerids`,
  which crosswalks mfl/sleeper/gsis). High-confidence, id-based.
- **FFC:** no id → resolve `(normalized_name, season nfl_team, position)` against
  `players` + that season's roster/`player_season_positions`, reusing
  `normalizer.player_ids.PlayerResolver`. Fuzzy fallback on name only with a confidence gate.
- Unmatched rows: store with `player_id = NULL` + `source_player_name`, and **count in
  `source_health.unresolved_*`** so coverage is auditable and matching can be re-run later
  without a re-pull.

### 5. Coverage probe + bookkeeping

Per `(season, source, requested_format)` record rows-pulled, rows-matched, fallback-used in
`source_health`, mirroring the Sleeper runner. This is the audit trail for "which seasons /
sources / positions actually have market data."

### 6. Read-only repository helper

`queries.player_adp_rows_for_season(session, season_id) -> dict[int, list[AdpRow]]`
(player_id → raw per-source rows). **Raw only** — the blend is dashboard math. Gate test:
fixture with 2–3 known ADP rows across sources asserts the helper returns them.

---

## Phase 2 — dz-dashboard (blend, score, render)

### 1. `analytics/adp.py` — the blend (new, pure, tunable)

The blend is metric math → it lives here, not upstream and not in `web/`.

- `ADP_SOURCE_WEIGHTS = {"ffc": 0.5, "mfl": 0.3, "sleeper": 0.2}` — an **editable
  proposal** with a documented rationale, echoed in the payload (same pattern as the impact
  weights). Renormalize over sources actually present for a player (so a 2010 FFC-only
  player blends to FFC alone, not a penalized 0.5).
- `blend_adp(rows) -> {composite_adp, contributing_sources, source_spread, n_sources}`.
  `source_spread` (max−min across sources, or stdev) is exported as a *consensus* signal —
  high spread = the market disagreed, so the reach/value read is softer.
- Carry `actual_format` + `format_fallback` through so the UI can flag a non-PPR fallback.

### 2. Wire into `analytics/draft.py`

- In `_season_picks`, attach per pick: `adp` (composite), `adp_delta`, `market_label`,
  `adp_available` / `adp_reason`, `adp_sources`, `adp_source_spread`, `adp_format` +
  `adp_format_fallback`. Keep these **orthogonal to** the existing scoring fields — do not
  let a missing ADP flip the scoring `available`, or vice versa.
- Extend `draft_value()` with market-axis leaderboards: `reaches` (most negative
  `adp_delta`) and `values` (most positive), each gated on `adp_available`, reusing
  `LEADERBOARD_LIMIT`. Add an `adp_definition` string.
- New `draft_tendencies(session, cache)` aggregate → per owner/team across all captured
  drafts: `reach_rate` (share of picks with delta < −band), `mean_delta`, `adp_discipline`
  (mean |delta| or delta stdev — lower = sticks to the board), positional reach breakdown,
  and `n_picks_with_adp` (the honest denominator). Owner prominence gated via the existing
  `owner_qualified_map`. Cache on the pipeline run like `_draft_history_model`.

### 3. API + client

Extend `DraftPick` / `DraftValue` schemas with the new fields; add a `DraftTendencies`
schema + `GET /v1/draft/tendencies` route (and reuse on the team page). Run
`npm run gen:api`; commit the regen; never hand-edit the client.

### 4. UI surfaces (`DraftPage.tsx` + team page) — all four, each toggle-able

1. **Per-pick ADP chip** — on `PickCell` + leaderboard rows: e.g. `ADP 23 · +11 value`
   (green) / `reach −8` (amber), with the format-fallback flag when `adp_format_fallback`,
   and a `DataGap`-lite chip (`reason={adp_reason}`) when no ADP. A high `adp_source_spread`
   gets a subtle "market split" hint.
2. **Reaches & Values leaderboards** — a new **Market** lens alongside Weighted/Points
   (extend the existing `Lens` type + `Tabs`), rendering `reaches` / `values` cards through
   the existing `LeaderboardList`.
3. **Reach × outcome quadrant** — a small scatter (x = `adp_delta` reach↔value, y = `impact`
   or `value` bust↔steal), only plotting picks with both numbers; quadrant labels tell the
   "reached & it busted" vs "late gem" story. New chart in `web/src/charts`.
4. **Manager / team draft tendencies** — a card on the team page (and optionally a
   league-wide records surface) from `/v1/draft/tendencies`: reach rate, mean delta,
   discipline, positional reach bars, with `n_picks_with_adp` shown so a thin sample is
   honest.

Each surface reads cleanly when its data is absent (no ADP for a season → chips become
gaps, leaderboards/quadrant empty-state, tendencies card hidden) — so hiding/retiring one
later is a one-line gate, not a refactor.

---

## Honest-gap handling (non-negotiable in this repo)

- **No invented ADP, ever.** Outside-top-~200 picks, most K/DST, rookies, retirees → no
  market data → `adp_available:false` + reason, surfaced via the gap affordance. Never 0,
  never a fabricated rank.
- **Format mismatch is disclosed,** not hidden: the league's custom scoring matches no
  public format exactly; chips/definitions say ADP is "{format}, 12-team consensus — the
  closest public market to this league, not its own valuations," and any fallback is flagged.
- **Sparse early years are expected.** 2010 (half-PPR target) is likely FFC-only and may
  hit the standard emergency fallback; pre-2018 has no Sleeper. The coverage probe makes
  this visible rather than silently degrading the blend.
- **Unmatched players counted, not dropped** (`unresolved_*`), so coverage is auditable.

## Test list

Phase 1: format-map + fallback unit (2010→half, 2011→full, miss→loud fallback); identity
match (id-based hit, fuzzy hit, unresolved counted); upsert idempotency; `source_health`
coverage rows; repository helper gate test on the fixture DB.
Phase 2: `blend_adp` (weight renormalization over present sources; spread); `adp_delta`
sign + `market_label` band; `draft_value` reaches/values ordering; `draft_tendencies`
(reach rate, discipline, honest denominator, owner gating); schema/`gen:api` drift;
DraftPage chip + lens + quadrant render tests; team tendencies card test.

## Done when

- `player_adp` exists and is backfilled 2010–2025 across the three sources (with the
  coverage probe recording the real per-season/source/format availability).
- `/v1/seasons/{id}/draft[/value]` carry the per-pick ADP fields; `/v1/draft/tendencies`
  returns per-owner/team market tendencies.
- All four UI surfaces render, each gracefully empty when ADP is absent, with the sign
  convention and format/fallback disclosed.
- Phase 1 gate green + real-DB backfill spot-check; Phase 2 full gate green + `gen:api`
  drift clean + manual click-through (2015 draft: reach/value chips, quadrant, a team's
  tendencies card).

## Open questions / risks

- **FFC half-PPR depth for 2010** — may not exist; confirm during the coverage probe and
  accept the (loud) standard fallback if so.
- **Blend weights** are a starting proposal; expect to tune once real spreads are visible.
- **FFC name matching** is the softest join — needs a confidence gate + an unresolved
  report to keep false matches out.
- **Roadmap placement** — add a P# row referencing this doc (two-phase, like the injury
  milestone) when scheduled.
