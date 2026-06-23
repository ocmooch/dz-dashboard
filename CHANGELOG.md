# CHANGELOG.md — dz-dashboard

Reverse-chronological history for completed passes, audits, and notable data-regeneration events.
Keep `PROGRESS.md` focused on current state. For the consolidated, fully-organized records see
`docs/archive/COMPLETED_WORK.md` (all finished work) and `docs/ACTIVE_WORK.md` (all remaining work).

## 2026-06-23 — Release v0.3.0 (dev → main promotion)

- **Version bumped `0.2.0` → `0.3.0`** (`pyproject.toml`, `web/package.json` + lock) and `dev`
  promoted to `main`, tagged `v0.3.0`. Minor bump: a large batch of new features since `v0.2.0`, no
  breaking changes (pre-1.0).
- **What landed since the last release (PRs #72–#100):** the Data Integrity & Coverage program
  (#77–#81), matchup superlative flags + source player-identity integrity + BFF-owned weekly division
  standings (#82–#84), the draft suite — genuine-zero classification, draft-impact composite,
  integrity follow-up, query perf, position taxonomy (#85–#89), the FAAB suite — bid capture +
  remaining-budget view (#90–#93), the 2022 Hamlin no-contest championship resolution (#94, #97),
  docs/state reconciliation (#95), Records-book accuracy & attribution (#96), and the **bonus-scoring
  fidelity** stack — BFF `authoritative_week_points()` coalesce layer (#99) — with its upstream data
  fixes landing in `danger-zone` v1.6.0, plus the box-score visual-baseline refresh (#100).

## 2026-06-22 — Records-book accuracy & attribution (feature/records-accuracy)

- **Corrected "Best player week."** It took the global `player_stats_scored` max, which (a) ranged
  over the **whole NFL** the pipeline scores — not just league-rostered players — and (b) used the
  nflverse reconstruction, which omits bonuses NFL.com applied (e.g. long-TD), under-scoring older
  games. The result crowned **Jahmyr Gibbs (2025, 63.4 recon)** over the true record. It now scopes
  to **started** roster rows and scores each the box-score way — preferring authoritative
  `extra_data.nfl_com_points`, falling back to the reconstruction — yielding **Doug Martin, 67.2,
  2012 wk9 (Sulladin's Salty Mujahideen)**, matching the NFL.com league-history page.
- **Attributed the matchup records.** `biggest_blowout` / `narrowest_win` exposed only a bare
  number plus a nested `winner` the grid never read, and `highest_scoring_matchup` carried only team
  ids. Each now carries both sides' season-correct names; the grid renders "<winner> def. <loser>"
  and "<team> vs <opponent>". `best_player_week` gains team/owner attribution. Records dict is
  `extra="allow"` → no `gen:api` drift. Fixture/test guards the non-rostered-exclusion regression
  (Lamar's higher unrostered 35.5 yields to McCaffrey's started 30.0). Gate green: backend 448,
  frontend 192.

## 2026-06-22 — 2022 Hamlin no-contest championship resolution (#94)

- **Corrected the 2022 fantasy championship.** The NFL Week-17 Bills@Bengals game was suspended
  (Damar Hamlin) and ruled a permanent no-contest, so the four affected BUF/CIN starters had no
  wk17 stat line and the DB stored the wrong champion. The box score now branches on the upstream
  `hamlin_substitute` flag (league methodology `final = wk17_partial + wk19`, wk18 skipped) before
  zero-classification — suppressing the false DNP, badging "Wk17+19" with the partial/wk19 split.
- A matchup-level `resolution_note` banner explains the substitution, and a provenance-gated curated
  `league_event` (`analytics/curated_events.py`) merges into the league timeline. Schema gains
  `HamlinSubstitute` + `resolution_note` (`gen:api` regenerated). Corrected title game = Smokin Doubs
  139.54 def. CMC 101.0; ranks swap (CMC 1→2, Doubs 2→1), only the championship flips. Pairs with
  danger-zone PR #54 (idempotent `overrides/hamlin_2022_wk17.py`). Gate green: backend 448, frontend 192.

## 2026-06-20 — 2026-06-21 — FAAB bids + weekly remaining-budget (#90–#93)

- **FAAB bid-capture confirmed + handed off** (#90): recorded the upstream gap and plan
  (`docs/handoffs/faab-bid-capture.md`); danger-zone then wrote `extra_data.faab_bid` on 2021–2025
  `waiver_add` legs (214/241/214/205/182 rows; pre-2021 null) — F-37.
- **Surface FAAB bids in the team transactions log** (#91): `analytics/teams._faab_bid()` now reads a
  **$0 bid as a real free claim** (394/1056 bids are exactly `$0`; the old `faab_bid or faab or bid`
  chain collapsed `0`→`None` by checking presence and returning `0.0`); the winning bid is promoted
  from the faint detail line to its own accent `"$X FAAB"` pill. BFF contract unchanged → no drift.
- **Weekly remaining-budget view** (#92/#93): pure `team_faab_budget()` derives per-week
  `remaining = budget_at_week − cumulative spend`; `GET /v1/teams/{id}/faab-budget`; `FaabBudgetCard`
  on the Team page. Season budget = flat **$100** base + mid-season per-team **credits** parsed from
  budget `setting_change` events (`team_id=NULL`, matched by team name), modeled as timestamped credits
  so the 2022 Ice Station Zebra **+$37 refund** reproduces (remaining never negative, lands at $0);
  Timeline events name the affected team + refund context. FAAB-era is **data-driven** on captured bids
  (pre-FAAB seasons return not-applicable, not a `DataGap`). Gate green: backend 438, frontend 191.

## 2026-06-18 — 2026-06-19 — Draft suite: genuine-zero, impact, integrity, perf, taxonomy (#85–#89)

- **Genuine-zero classification** (#85): drafted-but-never-played picks are real zeros with a DNP
  note, not gaps; a 5-way pick classifier replaces the bare-zero treatment.
- **Opportunity-cost-weighted draft impact** (#86): composite `value × cost_weight × opportunity_weight`
  (new reusable `analytics/weighting.py`); steals/busts ranked by impact (records book stays on raw
  value by decision); `ImpactTag` UI with a breakdown tooltip. Weights are an editable proposal.
- **Draft impact integrity** (#87): scoring resolves canonical identity clusters (2019 Mike Williams),
  rounds tiny differentials to positive `0.0`, and standardizes weighted impact within QB/RB/WR/TE so
  raw QB scale no longer monopolizes the headline; synchronized Weighted/Points leaderboards + filters.
- **Draft-page perf** (#88, BFF-only, byte-identical): a cold draft request had exploded to ~24k
  queries / 3.5s; the league-wide history sweep + per-season picks are memoized via `AnalyticsCache`
  and identity-cluster resolution is batched → `draft_value(2025)` cold 0.41s / 167 q, warm ~3 q.
- **Fantasy position taxonomy + resilient empty state** (#89, below).

## 2026-06-19 — Draft chart: fantasy position taxonomy + resilient empty state (#89)

- **Fold raw NFL positions onto the fantasy universe** (`{QB, RB, WR, TE, K, DEF}`) at the
  single source (`analytics/draft.py:_season_picks`). A new `fantasy_position()` /
  `_NFL_TO_FANTASY` table maps aliases and no-fantasy-slot positions to their clear home
  (FB→RB, PK→K, DST→DEF) and folds a two-way player listed at a defensive position to the
  offensive role he actually plays — Travis Hunter (2025), listed `CB` but drafted and
  scored entirely as a receiver, now resolves to `WR` (and so earns a weighted impact
  instead of being excluded). NFL-only positions with no fantasy home map to `None` rather
  than being guessed. This removes `CB` from the 2025 position filter. No contract change
  (`position` stays `str | null`).
- **The weighted-impact chart card no longer unmounts itself.** Selecting an ineligible
  position (K/DEF have no weighted impact) used to empty `chartRows` and unmount the whole
  card — *including its own filter dropdowns* — stranding the user until a browser refresh.
  The card now renders whenever there are picks; the chart area shows either the bars or an
  honest empty state ("…switch to the Points lens to compare them"), so the selection stays
  recoverable. Chart filters also reset on season change.

## 2026-06-18 — Division standings, matchup flags, identity integrity, Teams page (#80–#84)

- **BFF-owned weekly historical division standings** (#82): the presumed Phase 1 conference
  tables/columns do not exist in the live schema, so the dashboard now owns a reviewed NFL.com
  2010–2019 division artifact (120 rows) and returns exact matchup-derived weekly in-division records
  + source ranks, mapped through `teams.team_abbrev` with an honest mapping gap on mismatch. The
  Standings page renders complete historical division tables; 2020+ stays explicitly ungrouped. This
  **replaces the silently-dead conferences feature** (former OPEN_QUESTIONS N6 / ACTIVE_WORK §6.1).
- **Matchup superlative flags** (#83): a data-calibrated **60-pt blowout** threshold (≈ historical
  90th percentile, flags 10.6%; the prior 40-pt cutoff flagged 27%); flags shown on the grid + box.
- **Source player-identity integrity** (#84): an authenticated 2010–2025 draft/transaction sweep
  identified + repaired **34 external-ID ownership mistakes** upstream (strict audit now 0);
  `/v1/meta/coverage` exposes mismatch diagnostics and Coverage & About reports the verified state.
- **Teams nav + team-page refinements** (#80): a top-level Teams index (`/v1/teams`, grouped by
  season or owner); the schedule gains a W/L `ResultTimeline`; the Transactions + roster-diff cards
  merge into one collapsible week-grouped acquisitions feed; short weeks pad to the usual roster size
  with dashed empty slots (`is_empty`, derived from snapshots).
- **Refreshed stale visual-regression baselines** (#81).

## 2026-06-17 — Fold Power into Standings + merge Timeline space (#78, #79)

- **Merged `/seasons` and `/rules` into one Timeline space** (#79): the season league-changes view and
  the Rules & Eras view are unified into a single chronological surface.
- **Retired `/power` as a top-level space.** It duplicated Standings (both are
  season-state-as-of-week with a "rank by week" `RankFlow`); power is now a Standings
  `?lens=power` toggle. Frontend-only — `power_ranking`/`power_timeline` already accepted
  `through_week`, so a `WeekStepper` now exposes power for any week of any season.
- **Extracted** `web/src/features/power/PowerTable.tsx` + `usePower.ts` (shared by Standings
  and Playoffs); deleted the routed `PowerPage`; `/power` → `/standings?lens=power` redirect;
  removed the "Power" nav entry.
- **Playoffs** gained a read-only "Power at playoff entry" snapshot (end-of-regular-season
  ranking) linking to the week-by-week lens.
- **Model unchanged** (0.40·PF/g + 0.25·all-play% + 0.20·win% + 0.15·last-3-PF/g); the
  explainer was reframed to state it is a points-dominant lens, not a forecast.

## 2026-06-16 — Data Integrity & Coverage program + matchup context guards (#73–#77)

- **Data Integrity & Coverage program** (#76 handoffs, #77 dashboard): a structural fix for the
  recurring data-gap / wrong-`player_id` whack-a-mole. Adds `/v1/meta/coverage` (relevance vs feed
  coverage + reason codes), self-explaining projection gaps, and cross-source identity-split
  detection. Box-score / team-roster / player-scoring / player-insight reads consume canonical
  identity clusters (paired with the upstream `player_identity_links` crosswalk + identity-aware
  ingest). Hollow Sleeper projection rows (all-zero, pre-2018) render an honest gap, not a fake `0.0`
  (upstream prune took the live DB 522,143 → 40,759 projection rows). Units A/D dashboard + B/C/E
  upstream — see `docs/ACTIVE_WORK.md` §0.
- **DATA roster-drift false-positive cleanup** (#75): the per-player "roster drift" badge now counts
  a `draft` row (`direction=add`, week 0) as the first acquisition, clearing **800** false positives
  (drafted-then-re-added players); the routine start/bench slot-conflict badge branch was retired.
  **39** genuine flags remain in 2010 W2–W8 where the in-season transaction log starts at W6 (upstream).
- **NFL.com current-state-drift status guard** (#74): NFL.com stamps a player's *current* roster status
  onto historical weeks, so the box score showed IA/IR/SUS on players who clearly played. New
  `analytics/player_status.py` drops an incompatible availability/roster status whenever the player
  played; genuine DNPs keep their badge.
- **Matchup context clues + reconstructed-week handling** (#73): the BFF emits `context_label` /
  `context_detail`, roster/opponent/game status, and reserve eligibility; reconstructed audit-snapshot
  weeks (centralized in `analytics/roster_snapshots.py`) get one team-level banner instead of per-player
  noise and are excluded from week-over-week roster diffs.

## 2026-06-15 — CI: disable setup-uv cache prune (#72)

- Disabled the `setup-uv` cache prune to stop flaky post-job teardown failures.

## 2026-06-15 — Release v0.2.0 (dev → main promotion)

- **Version bumped `0.1.0` → `0.2.0`** (`pyproject.toml`, `web/package.json` + lock) and `dev`
  promoted to `main`, tagged `v0.2.0`. Minor bump: a batch of new features since `v0.1.0`, no
  breaking changes (pre-1.0).
- **What landed since the last release (PRs #59–#69):** resolve headline-only NFL.com setting edits
  (#59), playoffs championship/consolation bracket split (#60), league-wide rivalry insight bands
  (#61), tiered `/seasons` setting-change classifier (#62), stale-matchups/conferences mypy fixes
  (#63), dev e2e + format debt cleanup (#64), injury enrichment across box score + team roster (#65),
  Rivalries strength spread across Standings + manager profiles (#66), matchup zero-status semantics
  + CI drift guard (#67), documentation archive cleanup (#68), and the two-workflow CI split with
  path-scoped e2e (#69).

## 2026-06-15 — Documentation cleanup: merge-wave reconciliation + retire obsolete tooling

- **Reconciled the docs against the #61–#67 merge wave.** Every branch the prior docs called
  "awaiting PR" is merged to `dev` and promoted to `main`: rivalries-insights (#61), seasons
  league-changes (#62), baseline gate debt (#63/#64), injury enrichment (#65), engagement /
  rivalries-strength (#66), and matchup zero-status (#67). `PROGRESS.md`, `docs/ACTIVE_WORK.md`, and
  `docs/archive/COMPLETED_WORK.md` §3a updated; **there are now no open feature branches.**
- **Retired the completed review-fixes program tooling.** All fix-passes P1–P6 are merged, so the
  program is closed: deleted `docs/plans/REVIEW_FIXES_ROADMAP.md`, the `.claude/skills/fix-pass`
  skill, the manual `docs/handoffs/review-fix-pass.template.md`, and the six per-pass plan snapshots
  (`docs/archive/fix-P1…P6`). The canonical finding reference
  (`docs/reviews/2026-06-in-browser-review.md`) is kept; the still-open UP findings moved into
  `docs/ACTIVE_WORK.md` §2.
- **Folded the forward execution plan into `docs/ACTIVE_WORK.md`** and deleted the standalone
  `docs/plans/COMPLETION_ROADMAP.md` (its S2 shipped as #61; S1 conferences-repair and S8
  league-history detail now live in `ACTIVE_WORK`).
- **Pruned merged/superseded plan snapshots** (all summarized in `COMPLETED_WORK.md`, retained in git
  history): merged feature plans (engagement-rivalries-strength, rivalries-insights, the three
  seasons-league-changes docs, zero-score-gap-audit), the rejected owner-epithet proposal, the closed
  F-54 handoff (`season-correct-nfl-team-danger-zone`), and the archive snapshots
  `players-audit-dashboard`, `deferred-product-decisions`, `prerequisites`, `P0_DATA_READINESS`.
  Moved `seasons-league-changes-inventory.md` into `docs/archive/` as the surviving data reference.
- **Net:** `docs/` went from 44 markdown files to 22 — the numbered `00`–`10` design spec, the
  runbook + design handoff, the single forward doc (`ACTIVE_WORK.md`), one archive aggregate plus
  three references, one active upstream handoff, and the review reference. The remaining open work
  (conferences repair, the UP program, the gated league-history expansion) is unchanged.

## 2026-06-14 — Documentation refresh: merge-wave reconciliation + tech-debt escalation

- Reconciled the live docs against the merge wave that landed since 2026-06-08. The following are
  now **merged to `dev` and promoted to `main`** (PRs #56/#58) and were re-filed from "landed
  locally" into the archive: **P12 player injury reports + box-score enrichment** (PRs #52/#53),
  **commissioner history**, **playoffs/bracket** (caveated → true bracket #55 → championship/
  consolation split #60), **seasons/rules redesign + setting-gap resolution** (PRs #54/#59),
  **season-correct player NFL team (F-54)** (PR #51), and the **standings-500 fix** (PR #57).
- **Roadmap:** P12 marked ☑ (as-built status now P0–P12); milestone trackers in `PROGRESS.md` and
  `docs/archive/COMPLETED_WORK.md` updated. **Open questions:** N2 (bracket) moved to *shipped*;
  N5 notes F-54 closed; added **N6** for the baseline gate breakage.
- **The only un-merged dashboard work** is the `feature/rivalries-insights` branch (rivalry insight
  bands + `GET /v1/rivalries/insights`); PR to `dev` not yet opened.
- **Escalated long-standing tech-debt** (carried across many PRs as "pre-existing, unrelated"),
  now tracked as `docs/ACTIVE_WORK.md` §6.1 / open-question N6: (1) **conferences ORM model drift**
  — `analytics/conferences.py` references the unmapped `Team.conference_id` (3 mypy + 1 ruff
  errors) on a *live* route (`/v1/seasons/{id}/conferences`) also feeding `bracket.py`; the same
  drift forced PR #57's raw-SQL workaround; (2) **stale matchups tests** — `test_p5_matchups_unit.py`
  asserts a removed `lineup_score_gap`/`gap_delta` box field (2 pytest failures); (3) a minor ruff
  ambiguous-unicode error in `league_history.py`. The backend gate is red until these land.

## 2026-06-08 — Deferred product decisions (Q10–Q13) resolved; team avatars built (Q11)

- Settled the four genuinely-open deferred product decisions from `docs/10_OPEN_QUESTIONS.md`:
  **Q10 keep dark-only**, **Q12 keep laptop-first**, **Q13 no exports** (all reversible, doc-only),
  and **Q11 pull team logos from the DB**. Decision plan: `docs/archive/deferred-product-decisions.md`.
- **Q11 team avatars.** New read-only binary route `GET /v1/teams/{team_id}/avatar` streams a team's
  season logo from Phase 1's on-disk content-addressed asset store (new `ASSETS_ROOT` setting, default
  `<db_dir>/assets`; `assets_root` injected on `app.state` like the engine/cache). 404s cleanly on
  unknown/no-avatar/missing-file/unconfigured and rejects path traversal. The SPA's `Chip` gained an
  `avatarUrl` prop (img + monogram fallback on null/404/load-error); team chips across standings,
  power, bracket, matchups, stories, league-history, and home now pass `teamAvatarUrl(team_id)`.
  **Owner/manager photos stay a true source gap** (0 source rows; relate F-06). Endpoint is binary and
  excluded from the OpenAPI schema, so there is **no contract change / no `gen:api` drift**.
- Real-DB check: team 1 streams its exact JPEG bytes with an immutable cache header; unknown teams 404.
  Full gate green (backend pytest 235 + ruff + mypy; frontend gen:api no-drift + typecheck + Vitest).

## 2026-06-08 — Tracking reorganization (archive vs active aggregates)

- Split development tracking into two aggregate documents: `docs/archive/COMPLETED_WORK.md`
  (shipped milestones P0–P11, merged fix-passes P1–P6, audits, regen events, and resolved
  findings/questions) and `docs/ACTIVE_WORK.md` (current feature-branch packaging, the UP
  upstream program, league-history expansion, deferred product decisions, and housekeeping).
- Moved the merged fix-pass plans P4–P6 from `docs/plans/` into `docs/archive/` (P1–P3 already
  there) and updated the plan-doc references in `docs/plans/REVIEW_FIXES_ROADMAP.md`.

## 2026-06-06 — Documentation refresh and consolidation

- Reconciled live docs with F-51: per-player fantasy scoring (`player_stats_scored`) now spans
  2010–2025; the only unscored season is normally the current/in-progress one, and gap affordances
  are data-driven on the per-season `is_scored` flag.
- Moved completed plans and historical snapshots into `docs/archive/`, moved the design handoff to
  `docs/DESIGN_HANDOFF.md`, and condensed `PROGRESS.md` back to a cheap session read.
- Deferred follow-up: `pyproject.toml` still shows the pinned git fallback tag as `v1.0.0`; a future
  non-docs pass should bump that fallback to a release matching the live ≥1.2.0 avatar-column schema.

## 2026-06-06 — fix-pass P4 verification and F-53 upstream repair

- P4 build on `feature/fix-P4-transactions` added roster-diff transactions: backend
  `derive_roster_moves(session, team_id)`, additive `/v1/teams/{team_id}/roster-moves`, and the
  team-page **In-season moves** card. The existing transactions area was relabelled **Draft**.
- Full gate was green, but real-DB click-through found F-53: every season's week-1 roster snapshot
  was corrupt/placeholder data, which produced fabricated churn if rendered honestly.
- The danger-zone regen fixed F-53. Real-DB recheck confirmed week-1/week-2 overlap is normal,
  period-correct players are present, and the original team 184/2024 fabricated 68-add/67-drop case
  now returns wk1 adds=2/drops=0. No dashboard workaround or code change was needed after the regen.

## 2026-06-06 — fix-pass P2 redo and F-51 scoring reframe

- F-51 landed after the `fantasy.db` regen reconstructed pre-2016 per-player fantasy scoring.
  Live coverage changed from a 2016–2025 player-scored window to a 2010–2025 player-scored window.
- The F-51 dashboard pass removed stale pre-2016 gap copy, generalized player-detail unscored-tenure
  handling, kept every gate data-driven on `is_scored`, and verified the built SPA against the real DB:
  2010–2025 show scoring; the current unscored season shows the expected affordance.
- P2 redo updated the coverage harness away from hardcoded pre-2016 absence assumptions. It kept a
  synthetic fixture unscored season as a generic gap case, asserted records/player windows from
  `is_scored`, and verified 2010/2015/2025/current-season behavior on the real DB. PR #34 merged.

## 2026-06-06 — fix-pass P3 search

- PR #32 merged the search pass: league-scoped player search, NFL team/city/nickname expansion,
  fantasy team-name hits linking to managers, and hardening for LIKE wildcards, injection strings,
  regex metacharacters, scripts, and blank input.
- The F-50 real-DB blocker was resolved by regenerating the DB with ff-pipeline 1.2.0 avatar columns.
  P3 required no dashboard code change for that schema repair.
- The regen surfaced F-51 and F-52. F-51 was resolved by the scoring reframe; F-52
  (`seasons.status` all `in_progress`) remains upstream.

## 2026-06-04 — fix-pass P1 and P2

- PR #30 merged P1 analytics correctness/scoping/enrichment: season-schedule model, records era split,
  fantasy-week-capped season totals, owner-season result derivation, head-to-head cumulative margin and
  closest meeting, and matchup close/blowout plus entering-record fields. Real-DB verification showed
  a 2011 game can legitimately hold a team record.
- PR #31 merged the original P2 honesty pass under the then-current coverage premise: shared pre-2016
  gap copy, `season_unscored` / pre-2016-only player affordances, and the first coverage-integrity
  harness. This was later superseded by F-51 and preserved as historical context.

## 2026-05 — Players-view data-honesty audit

- Phase A made the player index league-relevant by default, enriched rows with rostered-season span
  and `has_scored`, collapsed ownership into spans, and added explicit bio gap affordances.
- Phase B added last-year-played, removed the unreliable nflverse active/retired UI signal, and folded
  rostered spans onto Phase 1's `Player.first_rostered_season` / `last_rostered_season` columns.
- B4 confirmed the contamination guard after the danger-zone D5 fix: duplicate cross-team roster groups
  and home/away lineup intersections were 0 on the real DB.

## 2026-05 — Phase 2 build completion

- Roadmap milestones P0–P11 shipped: read-only FastAPI BFF, generated-contract React SPA, home,
  standings, managers, matchups/box scores, rivalries, records, players, stats, team pages, draft,
  power rankings, search, coverage/about, operations, runbook, and e2e/visual-regression specs.
- The root README, `web/README.md`, `docs/PHASE2_RUNBOOK.md`, `Makefile`, and local service scripts
  documented daily operation.
