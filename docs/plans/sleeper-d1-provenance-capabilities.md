# Plan: Sleeper D1 — provenance + capabilities in the contract

**Milestone:** D1 (`docs/sleeper/02_DASHBOARD_BUILD_PLAN.md` "D1"). **Branch:**
`feature/sleeper-d1-provenance` → PR to `dev`. **Planned:** 2026-11-10.
**Cites:** `00_UPSTREAM_STATE.md` §2 (helpers), §3 (capability states + user rules), §6;
`01_DASHBOARD_ARCHITECTURE.md` §3.2, §4, §6; `03_CROSS_PLATFORM_UX.md` §1–§3.

## Scope

**Done when (verbatim):** every season-scoped payload carries platform + capabilities; Timeline
shows the "Moved to Sleeper — 2026" change; About shows the capability matrix.

**Tests (verbatim, `02` D1):** capability resolution per state; schema contract tests; parity test
still green (new fields excluded); component tests for the three primitives; lint/grep rule for
platform literals.

**Out of scope:** 2026 behavior fixes in analytics (D2/D3: points, provisional weeks, opponent-less
rows), official brackets (D5), FAAB/picks (D6), status (D7). No DB writes.

## Decisions (user, 2026-11-10)

1. **Season-level payloads only.** `SeasonListItem`, `SeasonSummary` and `LeagueTimelineSeason`
   carry `platform`, `platform_label` and `capabilities`. Pages read them through
   `SeasonContext`; the per-season endpoints don't repeat them.
2. **No Sleeper usernames.** `platform_accounts` = `platform`, `label`, `first_season`,
   `last_season`. It never includes `external_display_name` or user ids.
3. **The platform change shows right away**, even before 2026 has games. The "Moved to Sleeper"
   change and `platform_eras` are computed from the `seasons` table (any status, platform set),
   **not** from played seasons. The Timeline renders the change at 2026 although the unplayed
   season itself stays hidden (resultless-season rule unchanged).
   - **Approved golden impact:** the frozen golden DB holds the unplayed 2026 Sleeper row, so the
     live `/v1/league/eras` golden gains exactly one `changes` entry. BUILD confirms the diff is
     only that entry, then regenerates that single golden. Every other golden must stay green.

## BFF

| Path | Change |
|---|---|
| `src/ff_dashboard/analytics/platform.py` (NEW) | `season_provenance(s, season_id) -> {platform, platform_label}` via `queries.season_platform`. `season_capabilities(s, season_id) -> dict[key, {state, note}]` via `queries.season_capabilities`, with `not_used` notes forced to `None` (silent, `00` §3). `platform_eras(s) -> [{platform, label, start_year, end_year}]` over **all** seasons with a platform (decision 3), where `end_year` is None for the current platform. `capability_matrix(s) -> {keys, seasons: [{season_year, platform, cells}]}` for About. |
| `src/ff_dashboard/api/schemas.py` | NEW `Capability{state, note}`, `SeasonCapabilities = dict[str, Capability]`, `PlatformEra`, `PlatformAccount`, `CapabilityMatrix`. Additive optional fields: `SeasonListItem` / `SeasonSummary` / `LeagueTimelineSeason` get `platform`, `platform_label`, `capabilities`; `MetaResponse` gets `platform_eras`, `current_season_id`, `current_week`; `CoverageMatrix` gets `season_platforms: dict[year, platform]` + `capabilities: dict[year, SeasonCapabilities]`; `ManagerIdentity` gets `platform_accounts`; `LeagueEraChange` gets `platform_changed: bool = False`. |
| `src/ff_dashboard/analytics/league_history.py` | `league_eras` emits a `LeagueEraChange` (`platform_changed=True`, detail "Moved to Sleeper") at the first season (any status) of a new platform (decision 3). Playstyle era ids (`_era_key`) are **unchanged**: the platform is provenance, not a playstyle trait. |
| routes: `seasons.py`, `meta.py`, `league.py` (+ `owners.py` for managers) | populate the fields. A new `GET /v1/meta/capabilities` returns `CapabilityMatrix` for About. Adding a route is additive, and the D0 coverage test requires it to get a golden. |
| `analytics/coverage.py` | fills the two new `CoverageMatrix` maps |

`current_season_id` / `current_week` come from the in-progress season (`season_freshness`), or are
null when there isn't one.

## Frontend

| Path | Change |
|---|---|
| `web/src/lib/platform.ts` (NEW) | `platformLabel()`, `capabilityCopy` (the `03` §3 table, keyed by capability + state; a BFF `note` wins when present), `isRendered(cap)` (`not_used` → false). **The only place platform literals may appear.** |
| `web/src/app/shell/SeasonContext.tsx` | `SeasonInfo` gains `platform`, `platform_label`, `capabilities` |
| `web/src/design-system/index.tsx` | `EraMarker` (uppercase mono label, `--text-muted`, no brand colour, `03` §2); `CapabilityGate` (children when available/partial/derived; `DataGap` with `capabilityCopy` when `not_on_platform`/`not_yet`; **nothing** when `not_used`); `ProvenanceNote` (one-line footnote) |
| season header (AppShell / season pages) | `EraMarker` beside the season title |
| Timeline (`features/history` or wherever `LeagueEras` renders) | the platform change renders like any other era change, with the `EraMarker` boundary |
| `features/about/AboutPage.tsx` | platform eras + capability matrix table (seasons × capabilities, the state as text, `not_used` blank) |
| CI grep (`scripts/check_platform_literals.sh` + the ci.yml step) | fails on `"nfl_com"`, `"sleeper"`, `'NFL.com'` or `'Sleeper'` comparisons in `web/src` outside `lib/platform.ts` and generated `lib/api/` |
| `npm run gen:api` | regenerate the client (needs the BFF running on 8800 during BUILD) |

## Tests

- **Unit** `tests/test_platform_unit.py`:
  - Each state resolves (`available`, `partial`, `derived`, `not_yet`, `not_on_platform`,
    `not_used` with its note cleared).
  - `platform_eras` covers every season with a platform (decision 3): `[nfl_com 2015–null]` on the
    legacy fixture (the unplayed 2018 still counts as NFL.com), and
    `[nfl_com 2015–2018, sleeper 2026–null]` on the mixed fixture.
- **Contract** `tests/test_d1_endpoints.py` (mixed fixture):
  - `/v1/seasons` and `/v1/seasons/{id}` carry platform + capabilities for both eras.
  - `/v1/meta` platform_eras + current season/week; `/v1/meta/coverage` maps.
  - `/v1/league/eras` has exactly one `platform_changed` change, at 2026, with the "Moved to
    Sleeper" detail.
  - `/v1/meta/capabilities` matrix.
  - `platform_accounts` never contains user ids or usernames (per decision 2).
- **Parity:** `test_fixture_legacy_parity` + `test_fixture_parity_survives_a_sleeper_season` +
  `--check` on the live golden all stay green. The new fields are additive, so the subset rule
  passes. The new `/meta/capabilities` golden is added via the writer for the new route only. The
  existing goldens stay unchanged; any diff in them is a regression.
- **Components** (`web/src/design-system/index.test.tsx`): `EraMarker` text/uppercase;
  `CapabilityGate` for each state (renders children / `DataGap` with copy / nothing for
  `not_used`); `ProvenanceNote`. Page tests: About shows the matrix; Timeline shows the change
  (mock client).
- **Guard:** the platform-literal grep passes on the tree and fails on a planted literal (tested by
  the script's own self-check).

## Verify

Full gate (backend + frontend: gen:api drift, typecheck, lint, vitest). Click through About, the
Timeline and a season header against a **2026 DB copy**, built per the `00` §7 recipe: copy the
live DB, run the go-live sequence on the copy with `DATABASE_URL`, about 2 min with network. The
copy goes under `data/` (gitignored); never point it at the live DB.
