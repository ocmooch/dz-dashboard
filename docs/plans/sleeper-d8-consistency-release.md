# Plan — Sleeper D8: consistency pass and release

Branch: `feature/sleeper-d8-consistency-release` (from `dev` @ 0d3a8ae, after D7 merged as PR #134).
Sources: `docs/sleeper/02` D8, `docs/sleeper/03_CROSS_PLATFORM_UX.md` §1–§5, `docs/sleeper/00` §1,
the open items each D-plan left (below).

**Done when (verbatim):** the UX checklist passes on both eras; parity suite green; release tagged.

## State at planning time (probed 2026-11-10)

- **Live DB still has no 2026 games** (`seasons` 2026 = `sleeper`, 0 matchups). The go-live is
  upstream's and the user's to run (`00` §1); D8 never triggers it.
- **danger-zone `main` (v2.0.2) already has every S8 helper** the dashboard calls
  (`player_status_asof` etc.; `origin/main..origin/dev` is empty), so the deployed pairing works.
- `dev` is 94 commits ahead of `main` (last release `v0.4.0`). Versions: `pyproject.toml` and
  `web/package.json` both `0.4.0`.
- Visual baselines today: legacy only (`e2e/visual.spec.ts`: home, standings, records, rivalries,
  box score, standings mobile). No Playoffs baseline (left to D8 by D5), nothing for 2026.

## Decision for the user (asked before the release step, not before the walk)

**Release before or after the go-live?** Default: **before**. `v0.5.0` is the build that handles
2026 rows (D1–D7); promoting it first means the go-live lands on a dashboard that is already ready,
which is the order `00` §1 asks for. The 2026 walk therefore runs on the mixed-era fixture (and the
D7 scored copy for box scores), and a short re-walk of 2026 on live data becomes the first item
after the go-live (`ACTIVE_WORK`). The alternative (wait for the go-live, walk 2026 live, then
tag) is safer for 2026 copy but holds the release on an upstream step.

The `dev → main` merge and the tag are irreversible-ish shared actions: **ask for explicit go-ahead
at that step** even with the decision above.

## Work items

### 1. UX walk (`03` §5) — both eras

- Seasons: **2015, 2025** on the live DB (read-only BFF + built SPA on a scratch port), **2026** on
  the mixed-era fixture (`serve_e2e.py --mixed`, :8811) and, for box scores, a scored copy.
- Pages (21): Home, Timeline, Standings (+ power lens), Playoffs, Matchups, Box score, Team, Teams
  index, Managers, Manager profile, Rivalries, Pairwise, Records, Players, Player detail, Stats,
  Draft, Stories, Viz Lab, Insights Lab, About.
- Method: one scratch Playwright script (scratchpad, not committed) that screenshots each page per
  season in dark and light; read the shots, not the DOM. Record one row per page in the as-built
  table below: ✓ / finding id.
- The eight checks per page: same layout/components/gap states; era marker only in season
  header / Timeline / cross-season chart boundary; no `0` for a missing capability; labels per §4;
  `AggregationNote` on 2025→2026 aggregates that exclude/normalize; provisional weeks marked,
  finalized weeks identical to legacy; 2026 avatars from the asset store at legacy size/crop;
  light/dark parity.
- Also grep-level checks: `scripts/check_platform_literals.sh`; no `EraMarker` outside the three
  allowed places (`git grep -n EraMarker web/src`); `capabilityGapText` copy matches `03` §3.

### 2. Fix findings — bounded

Fix small, presentation-level findings in this branch (copy, missing note, wrong component). Any
finding that needs new analytics or a contract change goes to `ACTIVE_WORK.md` with its id, not into
D8 ("don't merge milestones"). Each fix gets a test at the level it lives (vitest or pytest).

### 3. Inherited open items — triage

| From | Item | D8 action |
|------|------|-----------|
| D1 | visual click-through never done | covered by the walk (item 1) |
| D5 | Playoffs visual baseline | **do**: add to the baselines (item 4) |
| D5 | 2010–2019 divisions view has no Potential points | → `ACTIVE_WORK` |
| D6 | market % of budget ignores mid-season credits; `is_move` unused | → `ACTIVE_WORK` |
| D7 | `*` bench-or-reserve hint doesn't use the Sleeper IR status | → `ACTIVE_WORK` |

### 4. Visual baselines per era

- Legacy (`visual.spec.ts`): add `playoffs` (fixture 2017 bracket).
- Sleeper: new `e2e/sleeper-visual.spec.ts` on the `sleeper` project (widen the
  `SLEEPER_SPECS` regex in `playwright.config.ts` to `/sleeper(-visual)?\.spec\.ts$/`): home,
  standings, playoffs, matchups week 9 (pending), team page. Mask `.dz-data-status`.
  **Leave out Player detail**: its "latest" card depends on today's date (7-day rule) and would
  flake; the `sleeper.spec.ts` journey already covers it functionally.
- Generate with `--update-snapshots` on the new tests only; confirm no existing baseline changed
  (`git status web/e2e/*-snapshots`).

### 5. Docs

| Doc | Section | Change |
|-----|---------|--------|
| `docs/03_DATA_ACCESS.md` | Reliability map | Sleeper-era rows: provisional weeks, failed claims, pick/FAAB legs, official brackets, status snapshots (7-day), `not_used` |
| `docs/05_API_CONTRACT.md` | endpoint list | D1–D7 routes: `/v1/meta/capabilities`, `/v1/seasons/current`, `/v1/seasons/{id}/faab-market`, `/v1/league/picks`, `/v1/players/{id}/status`, plus the additive fields (`platform`, `capabilities`, `aggregation_note`, `scoring_era`, `injury_source`, …); one line each, link the D-plan |
| `docs/07_PAGES_AND_VIEWS.md` | affected pages | Home ThisWeek, Team trade/lost bids, Stats FAAB market, Draft pick ledger, Player Status card, Playoffs official bracket |
| `docs/09_ROADMAP.md` | new "Sleeper era" rows | D0–D8, each → its plan, status done |
| `docs/ACTIVE_WORK.md` | §0 + §5 | the items routed in 2–3, plus "re-walk 2026 on live after go-live" |
| `CHANGELOG.md` | top | D0–D8 summary + "Release v0.5.0" entry (mirror the v0.4.0 entry) |
| `PROGRESS.md` | Current state | Sleeper program done; next = go-live re-walk |

### 6. Release (after explicit go-ahead)

1. Bump `0.4.0 → 0.5.0` in `pyproject.toml`, `web/package.json` + lock (`npm version --no-git-tag-version`),
   `uv lock` (ff-pipeline version moves in `uv.lock` are expected; commit them).
2. Full gate (green-gate skill) incl. e2e and `snapshot_legacy_payloads.py --check` (live 1092/0).
3. PR `feature/sleeper-d8-consistency-release → dev`; merge after CI; delete branch.
4. PR `dev → main` ("Release v0.5.0"); merge after CI.
5. Tag `main` `v0.5.0`, push the tag. Minor bump: new features, no breaking contract change
   (all additions are additive; parity proven).

## Tests

- Unit/contract: only for fixes made in item 2.
- Parity: `test_legacy_parity` (fixture) + live `--check`; no golden regenerated.
- e2e: full suite incl. the new `sleeper-visual` + legacy `playoffs` baselines.
- Grep checks: forbidden-import, platform literals, `EraMarker` placement.

## Done-when checklist

- [ ] Walk table complete for 21 pages × {2015, 2025, 2026}, dark + light; every finding fixed or routed
- [ ] Playoffs legacy baseline + Sleeper baselines added; no existing baseline changed
- [ ] Docs updated (table in item 5)
- [ ] Full gate green; live parity 1092/0
- [ ] User go-ahead → `dev → main` merged, `v0.5.0` tagged and pushed
- [ ] `PROGRESS.md` + this file's as-built updated

## As built

(walk table and notes go here in the BUILD session)
