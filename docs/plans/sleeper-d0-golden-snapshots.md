# Plan: Sleeper D0 — mixed-era fixture + legacy golden snapshots

**Milestone:** D0 (`docs/sleeper/02_DASHBOARD_BUILD_PLAN.md` "D0"). **Branch:**
`feature/sleeper-d0-golden-snapshots` → PR to `dev`. **Planned:** 2026-11-10.
**Cites:** `00_UPSTREAM_STATE.md` §1, §5, §6, §7; `01_DASHBOARD_ARCHITECTURE.md` §8.

## Scope

**Goal (verbatim):** prove later that nothing about 2010–2025 changed.

**Done when (verbatim):** golden snapshots exist for every `/v1` endpoint × representative legacy
seasons/ids; the parity test passes on `dev` unchanged; the fixture builder can produce the
mixed-era DB.

Two snapshot sets, because the parity baseline has to be both real and committable:

| Set | Source DB | Stored | Runs in |
|---|---|---|---|
| **Live golden** | a frozen copy of the pre-go-live live DB (below) | JSON **outside git** (real names); manifest + sha256 hashes committed | local only (skipped without the golden DB) |
| **Fixture golden** | the mixed-era fixture DB (pseudonymized, built in tests) | JSON committed under `tests/golden/fixture/` | CI + local |

### Deviation from `02` D0, approved by the user (2026-11-10)

`02` says to snapshot "against the **live** DB". The user chose to snapshot from the pre-go-live
backup instead: **"start dashboard D0 golden snapshots from the backup"**. That file is
`../danger-zone/data/backups/fantasy-pre-guard-v2-20261110T140400Z.db`. It was taken 2026-11-10,
just before upstream `migrate up`. It has no 2026 league data, and its legacy rows equal the live
DB's (upstream `legacy verify` passed on both).

This is stronger than a live snapshot. The parity test re-runs the BFF against the **same frozen
file**, so a failure can only mean dashboard code changed. Data drift can't cause one: the
go-live, nflverse refreshes on sealed years, and rescoring all leave the file alone. It also makes
all-time endpoints (records, owners, rivalries) comparable. On a live DB they change legitimately
once 2026 games are played.

## The frozen golden DB

- `data/golden/fantasy-golden-20261110.db` (repo-local, gitignored via `/data/`). Made by the
  SQLite backup API from the upstream backup file, never by touching the backup itself. Then
  `PRAGMA journal_mode=DELETE` on the copy, so it opens read-only without `-wal`/`-shm` files.
  Then `chmod a-w`.
- Its sha256 goes in the committed manifest. The live parity test refuses a file whose hash
  differs.
- Schema: revision `b8d0f2a4c6e3` (S3–S8, before guard v2). The only difference from head is
  trigger DDL, so reads are identical. **If a later milestone needs a newer upstream migration**,
  that milestone makes a new golden copy and runs `migrate up` on the copy. It records the new
  sha256 and confirms with upstream `legacy verify` against the copy that the legacy rows are
  untouched. The JSON baseline doesn't change.

## Files

| Path | What |
|---|---|
| `scripts/snapshot_legacy_payloads.py` | `--freeze <backup>` makes the golden DB copy. `--write` builds the request matrix and stores the JSON plus manifest. `--check` re-runs and diffs. Runs the BFF in-process (`create_app(create_readonly_engine(url))` + `TestClient`); no server, no writes. |
| `data/golden/live/<slug>.json` | live golden responses (gitignored) |
| `tests/golden/live_manifest.json` | committed: golden DB sha256, upstream revision, the request list (URL path + query only; ids, no names), the sha256 of each response, and the volatile-field exclusions |
| `tests/golden/fixture/<slug>.json` | committed fixture golden responses |
| `tests/sleeper_fixture.py` | mixed-era fixture builder (below) |
| `tests/conftest.py` | new session fixture `mixed_era_db_path` + `mixed_client`; the existing `fixture_db_path` is unchanged |
| `tests/test_legacy_parity.py` | the parity tests (below) |
| `tests/test_mixed_era_fixture.py` | fixture builder assertions |
| `PROGRESS.md`, `docs/08_TESTING_STRATEGY.md` (golden section) | docs |

## Request matrix ("every `/v1` endpoint × representative legacy seasons/ids")

- **All 48 `/v1` routes** (excluding `/health`, the SPA catch-all, and `/v1/teams/{id}/avatar`,
  which is binary; its bytes hash goes in the manifest instead). BUILD lists each route's query
  params from its signature. Every season-dependent request pins an **explicit legacy season**, so
  defaults ("latest season") never decide what's in the snapshot.
- **Seasons:** 2010 (6-pt pass TD + 0.5 PPR), 2013 (2011–15 rules), 2016 (first stable-rules
  year), 2020, 2024, 2025 (last NFL.com season). Each request also runs once with defaults, as a
  separately flagged "default" entry. Its expected change at go-live is documented, not asserted.
- **Ids, picked by a deterministic query recorded in the manifest:**
  - Per season: every team, one regular-season and one playoff matchup (the lowest `matchup_id`
    of each).
  - All owners.
  - Players: per season, the top scorer at QB/RB/WR/TE/K/DST, plus one player with a scoring gap
    and one with no stats.
  - The two-owner pairs for rivalry.
- **Volatile fields:** BUILD runs `--write` twice and lists every JSON path that differs (e.g.
  generated-at timestamps) as an exclusion in the manifest. The run should come out at roughly
  400–700 requests.

## Comparison rule (additive changes allowed)

`golden ⊆ current`. Every key and value in the golden JSON must be present and equal in the current
response. New keys are allowed (D1 adds `platform`, `capabilities`). List order counts, floats
compare exactly (same DB, same code path), and excluded paths are skipped. A failure prints the
request, the JSON path, and the golden vs current values. For the live set it never prints whole
payloads, because those contain names.

## Mixed-era fixture builder (`tests/sleeper_fixture.py`)

Approved (`00` §7): tests may run `ff_pipeline` loaders. `src/` stays read-only, and the
forbidden-import grep still covers only `src/ff_dashboard`.

- Start from a copy of the existing `fixture_db_path` DB (the legacy NFL.com seasons all current
  tests use). Add a Sleeper 2026 season sharing owners, loaded from upstream's pseudonymized
  fixtures in `../danger-zone/tests/fixtures/sleeper_league/season_2026/` + `synthetic/`. CI already
  checks out danger-zone `dev` as `../danger-zone`.
- Load through the **packaged** loaders (`load_league_season` / `normalize` + `load_season`), the
  same path as upstream `tests/integration/test_sleeper_load.py` `_prepare`/`_load` and
  `test_sleeper_rich.py` `_decided`. Upstream's test helpers (`fixture_league`, `OverlaySource` in
  `tests/unit/test_sleeper_normalizer.py`) aren't packaged, so BUILD re-implements their few
  lines here instead of importing an upstream test module.
- The `01` §8 checklist is asserted in `test_mixed_era_fixture.py`: a co-owner, a commissioner
  override, a failed bid, a pick trade, official brackets, a blank team name, and one capability gap
  per era. Anything the upstream fixtures lack is added as a small synthetic overlay in the
  builder, and each one is listed in the test.

## Tests

- `test_legacy_parity.py::test_fixture_legacy_parity` (CI): `mixed_client` against
  `tests/golden/fixture/`. It covers every `/v1` route for the fixture's legacy seasons. With
  2026 loaded in the fixture, explicitly pinned legacy requests must still equal the golden JSON
  written from the **legacy-only** fixture. That's the in-CI preview of the go-live.
- `test_legacy_parity.py::test_live_legacy_parity` (local): skipped unless
  `data/golden/fantasy-golden-20261110.db` exists with the manifest hash. Runs the full live matrix
  against `data/golden/live/` and checks each stored file's sha256 against the manifest.
- `test_mixed_era_fixture.py`: the builder's feature checklist; the Sleeper season is `platform =
  'sleeper'`; legacy seasons' row counts are unchanged by the build.
- A guard that the snapshot script never opens a writable engine: grep for `create_engine(` and
  `_create_writer` in `scripts/snapshot_legacy_payloads.py`.

**"Passes on `dev` unchanged":** after the BUILD commit, both parity tests are green with no edits
to `src/`. VERIFY runs the full gate once.

## As built (2026-11-10)

- The live matrix has 1,091 requests (all 55 `/v1` routes; 1,090 return 200 and 1 is the
  avatar-less 404). There are 0 volatile paths across two runs, `--check` shows 0 failing, and it
  takes about 40s.
- The fixture matrix has 333 requests, 254 of them pinned. All pinned ones hold on the mixed-era
  fixture, with no expected-diff list needed.
- The avatar requests cover every selected team that has one, plus one without. Bytes are hashed
  and read from upstream's content-addressed store (live), not from the frozen DB.
- The upstream fixtures already had the blank team name (1 user, shown as the "<owner>'s Team"
  fallback). The commissioner move is the only overlay the builder adds.
- `--freeze` opens the source backup with `immutable=1`. An earlier `mode=ro` open created empty
  `-wal`/`-shm` files next to the backup; they were checked as empty and removed, and the backup
  passed `quick_check`.

## Out of scope

No `src/ff_dashboard` changes, no frontend, no 2026 behavior (D1–D3), no live go-live.
