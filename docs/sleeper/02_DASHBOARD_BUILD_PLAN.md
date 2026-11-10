# 02 — dz-dashboard Build Plan: Sleeper Era

**Status:** planned, not started · **Repo:** `dz-dashboard` · **Branch per milestone:** `feature/sleeper-d<N>-<name>` → PR to `dev`
**Architecture:** `01_DASHBOARD_ARCHITECTURE.md` · **UX rules:** `03_CROSS_PLATFORM_UX.md`
**Upstream gates:** `../danger-zone/docs/sleeper/02_PIPELINE_BUILD_PLAN.md`

Follow the repo's plan → build → verify session model: each D-milestone gets a
`docs/plans/sleeper-d<N>-<name>.md` written in its PLAN session, citing only the sections below.
`PROGRESS.md` is updated at every checkpoint. Full gate at the end of each milestone.

---

## Milestone summary

| # | Milestone | Est. | Waits for upstream | Delivers |
|---|-----------|------|--------------------|----------|
| D0 | Mixed-era fixture + legacy golden snapshots | 2–3 hr | G1 (S3 schema) | test foundation; parity baseline |
| D1 | Provenance + capabilities in the contract | 2–3 hr | G2 (S5) + S8 helpers | `platform`, `capabilities`, platform eras, Timeline era change |
| D2 | Source-neutral points swap | 1–2 hr | G3 (S6 + S8) | `scoring.py` delegates upstream; parity proven |
| D3 | Current-season experience | 3–4 hr | G2 | Home command center, Sleeper weeks in Matchups/Box score/Standings |
| D4 | Cross-era aggregation audit | 3–4 hr | G3 | `aggregation.py`; careers, records, rivalries, power, insights era-aware |
| D5 | Official brackets + divisions + potential points | 2–3 hr | G4 (S7) | Playoffs/Standings upgrades |
| D6 | Transaction market: FAAB, failed bids, trades with picks, pick ledger | 3–4 hr | G4 | new views on Team/Stats/Draft |
| D7 | Player status + profile enrichment | 2 hr | G4 | Player detail status timeline, box-score badges for 2026 |
| D8 | UX consistency pass, visual baselines per era, docs, release | 2–3 hr | G5 | v-next promotion |

Total ≈ 20–28 focused hours. D3 can start as soon as G2 lands; D5–D7 are independent of each other.

---

## D0 — Mixed-era fixture + legacy golden snapshots

**Goal:** prove later that nothing about 2010–2025 changed.

Files: `tests/conftest.py` fixture builder (add a Sleeper-era season per `01` §8), new
`tests/golden/` snapshot set, `tests/test_legacy_parity.py`, `scripts/snapshot_legacy_payloads.py`
(runs the BFF in-process against the **live** DB read-only and stores JSON for 2010–2025 per
endpoint, outside git if it contains names; hashes committed).

**Done when:** golden snapshots exist for every `/v1` endpoint × representative legacy seasons/ids;
the parity test passes on `dev` unchanged; the fixture builder can produce the mixed-era DB.

## D1 — Provenance + capabilities

Files: `analytics/platform.py`, `api/schemas.py` (`SeasonCapabilities`, fields on `SeasonListItem`,
`SeasonSummary`, `LeagueTimelineSeason`, `MetaResponse`, `CoverageMatrix`, `ManagerIdentity`),
routes for seasons/meta/league, `league_history.py` (platform change as a `LeagueEraChange`),
`web/src/app/shell/SeasonContext.tsx`, `web/src/lib/platform.ts`, design-system `EraMarker`,
`CapabilityGate`, `ProvenanceNote`; `npm run gen:api`.

Tests: capability resolution per state; schema contract tests; parity test still green (new fields
excluded); component tests for the three primitives; lint/grep rule for platform literals.

**Done when:** every season-scoped payload carries platform + capabilities; Timeline shows the
"Moved to Sleeper — 2026" change; About shows the capability matrix.

## D2 — Source-neutral points

Files: `analytics/scoring.py` (aliases over upstream expressions), call sites unchanged.

Tests: parity suite green; a Sleeper-era box score shows official points from `platform_points`;
`authoritative_week_points` equals the old expression for every legacy fixture row.

**Done when:** no surface reads `nfl_com_points` directly except through the upstream helper.

## D3 — Current-season experience

Files: `analytics/current_season.py`, `GET /v1/seasons/current`, Home page, `DataAsOf.tsx`
(current week), Matchups/Box score (Sleeper weeks, commissioner override flag, provisional week
state), Standings (in-progress), `seasonPhase.ts`.

Tests: provisional vs finalized weeks; in-progress season excluded from records except completed
weeks; Box score for a Sleeper week mirrors a legacy box score's structure; e2e journey
"Home → this week's matchup → box score" on the mixed fixture.

**Done when:** the 2026 season is browsable end to end with the same look as 2025.

## D4 — Cross-era aggregation audit

Files: `analytics/aggregation.py`; adopt it in `owners.py`, `owner_story.py`, `records.py`,
`rivalries.py`, `head_to_head.py`, `power.py`, `efficiency.py`, `transactions.py`, `insights.py`,
`league_history.py`. Add `AggregationNote` to affected schemas.

Method: inventory every metric that spans seasons (grep for season loops / `GROUP BY owner`), apply
the rules in `01` §5, and record each decision in the D4 plan.

Tests: one unit test per rule in `01` §5; career totals include 2026 regular-season games; activity
metrics exclude lineup changes across all eras (and the legacy-only lineup view still works);
FAAB comparisons by % of budget; parity suite updated **only** where a rule intentionally changes a
legacy-era aggregate — each such change listed in the PR body for user approval.

**Done when:** every cross-season payload carries an aggregation note where it excluded or
normalized anything; no cross-era number silently mixes incomparable inputs.

## D5 — Official brackets, divisions, potential points

Files: `analytics/brackets.py` (reuses `bracket.postseason_classification` for legacy),
`GET /v1/seasons/{id}/brackets`, Playoffs page (placements, toilet bowl, 3rd place), Standings
(official divisions; potential points with `ProvenanceNote`).

**Done when:** 2026 playoffs render from official brackets; legacy brackets look identical to today
with a "derived" provenance note; Sacko derivation agrees on both.

## D6 — Transaction market

Files: `analytics/faab_market.py`, `analytics/picks.py`, `GET /v1/seasons/{id}/faab-market`,
`GET /v1/league/picks`, Team page (FAAB section gains failed bids), Stats (league FAAB market tab),
Draft page (pick ledger tab), transaction rows (trade assets: players + picks + FAAB).

**Done when:** a 2026 trade shows all its assets; bid wars visible; legacy seasons show the
capability gap for failed bids with the shared copy.

## D7 — Player status

Files: `analytics/player_status.py` (merge sources), `GET /v1/players/{id}/status`, Player detail
status timeline, `InjuryBadge` sourcing for 2026 box scores.

**Done when:** 2026 box scores show injury designations again (the post-2024 gap closes going
forward); 2025 remains an honest gap.

## D8 — Consistency pass and release

Tasks: walk every page for both eras against `03_CROSS_PLATFORM_UX.md`; visual baselines per era;
update `docs/03_DATA_ACCESS.md` reliability map (Sleeper rows), `05_API_CONTRACT.md`,
`07_PAGES_AND_VIEWS.md`, `09_ROADMAP.md` (Sleeper-era rows), `ACTIVE_WORK.md`, `PROGRESS.md`,
`CHANGELOG.md`; full gate incl. e2e; `dev → main` promotion with tag.

**Done when:** the UX checklist passes on both eras; parity suite green; release tagged.

---

## Per-PR checklist

- [ ] No DB writes; forbidden-import grep clean
- [ ] No metric math in `web/`; no platform-literal branching outside `lib/platform.ts`
- [ ] `npm run gen:api` run; client not hand-edited; drift check clean
- [ ] Legacy parity test green (or intentional changes listed for approval)
- [ ] Missing data renders `DataGap` with a capability reason — never `0`
- [ ] Docs + `PROGRESS.md` updated; commit trailers per `CLAUDE.md`
