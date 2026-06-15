# PROGRESS.md — dz-dashboard (Phase 2)

The single source of truth for "where we are." **Read this first every session** instead of
re-scanning `analytics/` and `web/`. Keep it short and current — update it at every checkpoint
and at the end of every milestone. This file is what makes the plan/build/verify split cheap.

How to use it (see `CLAUDE.md` + `.claude/skills/milestone-session`):
- At session start, read this, then the one `P{N}` row in `docs/09_ROADMAP.md`, then the plan
  (`docs/plans/P{N}-*.md`) if one exists. Stop there — don't browse the tree.
- At session end / checkpoint, update **Current state**, **Next**, and **Files that matter now**.
- Historical fix-pass and audit narrative lives in `CHANGELOG.md`.
- **Aggregated records:** all finished work → `docs/archive/COMPLETED_WORK.md`; all remaining /
  in-progress work, blockers, and open decisions → `docs/ACTIVE_WORK.md`.

---

## Current state

- **Everything below P12 is now merged to `dev` (and promoted to `main` via PRs #56/#58).** The
  only un-merged dashboard work is the rivalries-insights branch (see next bullet). The aggregate
  history lives in `docs/archive/COMPLETED_WORK.md`; the remaining open scope in
  `docs/ACTIVE_WORK.md`.

- **Engagement / "Rivalries strength" spread — building on `feature/engagement-rivalries-strength`
  (cut from `dev`), awaiting PR.** Spreads the Rivalries lens across the app by tier (plan +
  noise guardrail in `docs/plans/engagement-rivalries-strength.md`). **Item A shipped (Tier 2):**
  the Standings "Schedule Luck" card is reframed as **"Robbed & Blessed"** — two voiced callouts
  (most-robbed = lowest `luck_delta`, most-blessed = highest) lead the existing ranked list, each
  deep-linking to the manager profile (`/managers/{owner_id}`); rows now link to profiles too.
  The pick is **server-side** (`standings_insights` returns `most_robbed`/`most_blessed`, ties →
  lower `team_id`) to keep the frontend math-free; `StandingsInsights` schema + client regenerated
  (no drift). Per-season scope unchanged; unavailable seasons (e.g. seeded-but-unplayed 2018) stay
  `DataGap`, never a 0. Tests: extended `test_p2_analytics_unit.py` (picks/tie-break/unplayed-gap)
  + `test_p2_endpoints.py` + `StandingsPage.test.tsx` (callouts render + link + DataGap).
  **Item B shipped (Tier 3):** the Manager-profile **"Your Story"** lead band. New pure reducer
  `analytics/owner_story.py:owner_story()` over `head_to_head.all_pairwise()` + per-season
  `standings_insights` luck + `owner_seasons`, surfaced at `GET /v1/owners/{id}/story`
  (`OwnerStory` schema; client regenerated, gen:api stable). Superlatives: signature win (biggest
  beating), heartbreak (closest loss, prefers a playoff elimination), high-water mark, nemesis +
  favourite victim (reuse `MIN_NEMESIS_GAMES=3`), luckiest/unluckiest season (**sign-gated** — a
  "luckiest" line only when max `luck_delta`>0, "robbed" only when min<0). Every gated-out
  superlative is **absent (None)**, never a forced 0; each present line deep-links (box score /
  pairwise). Frontend `ManagerStory.tsx` (mirrors `RivalryInsights.tsx`) renders as the lead band
  above the existing cards; omits absent lines; hides entirely when nothing clears. Tests:
  `test_owner_story.py` (Maverick rich case + Viper sparse-but-valid + both sign gates + min-sample)
  + `test_p2_endpoints.py` + extended `ManagerProfilePage.test.tsx`. The **per-manager epithet** is
  built as a SEPARATE reviewable proposal — `assign_epithet()` + documented/tested thresholds, but
  **NOT wired** into the endpoint/UI; awaiting product-owner sign-off (`docs/plans/owner-epithet-proposal.md`).
  Full gate green (330 backend / 162 frontend). VERIFY (click-through + epithet sign-off) pending.

- **Rivalries page insight bands — landed on `feature/rivalries-insights`, awaiting PR to `dev`
  (the only open local branch).** Five league-wide bands below the rivalry matrix fed by one bundle
  endpoint `GET /v1/rivalries/insights` (`api/routes/rivalries.py` → `analytics/rivalries.py`, built
  on `head_to_head.all_pairwise`): **Hottest Rivalries**, **Rivalry Superlatives** (reuses the
  previously-dead `closest_rivalry()`), **Win Streaks**, **Nemesis & Favorite Victim**, and
  **Playoff Rivalries**. All math in Python; min-sample gates are documented constants
  (`MIN_INTENSITY_GAMES=4`, `MIN_NEMESIS_GAMES=3`, `MIN_ACTIVE_STREAK=3`); every row deep-links;
  missing data renders `DataGap`. Frontend pure presentation (`RivalryInsights.tsx`). Real-DB spot
  check (2026-06-12): all 5 bands `available:true`. New backend test file (7 tests) + extended page
  test pass; full frontend gate green (153 Vitest + typecheck + gen:api no-drift + build). Plan:
  `docs/plans/rivalries-insights.md`.

- **/seasons league-changes tiered classifier — built on `feature/seasons-league-changes`
  (cut from `dev`), awaiting PR.** Replaces the old 6-regex `_SETTING_PATTERNS` (silently dropped
  ~88% of 267 `setting_change` rows) with a full auditable classifier in new
  `analytics/league_changes.py`: every row → canonical type · tier (T1/T2/T3) · human label ·
  rephrased sentence · off/in-season phase · aggregate-to-event · 2021 re-attribution, **nothing
  dropped** (catch-all → T3). `WEEK1_KICKOFF` table validated against the 267-row phase oracle.
  `league_history.league_timeline()` feeds it the resolved-category set so roster/scoring headlines
  are absorbed by the state-table diff. `LeagueChangeDetail` schema extended (tier/phase/
  human_label/members/missing_context/canonical_type) + client regenerated; `LeagueHistoryPage.tsx`
  renders the 3 tiers, in-season marker, missing-context affordance, and expandable members.
  Real-DB check (2026-06-14, `../danger-zone/data/fantasy.db`): 264 leaves + 3 state-absorbed =
  267 (nothing dropped); FAAB merge, division realignments, 2014 schedule rebuild, 2018 waiver
  reorder, 2021 Adjusted-Pts, commissioner-handoff noise filter all correct. Tests: new
  `tests/test_league_changes.py` (classify/phase-oracle/aggregation, no DB) + fixture-backed
  integration in `tests/test_league_history.py` (seeded 2016 `setting_change` rows). Backend
  298 pass + ruff/mypy clean; frontend 153 pass + typecheck. Plan:
  `docs/plans/seasons-league-changes-IMPL-PLAN.md`.

- **Injury-report enrichment (extends P12) — built on `feature/injury-enrichment` (cut from
  `dev`), awaiting PR.** P12 surfaced only `report_status` + `report_primary_injury` on the box
  score; this folds in the two unused upstream fields (`practice_status`, `report_secondary_injury`)
  and adds the badge to the **week-scoped team roster** as well. New shared normalizer
  `analytics/injuries.py` (`injury_fields`) decides what counts as a real designation (gates to
  Out/Doubtful/Questionable/Probable; blank/"Note" → no badge), a real body part (drops nflverse
  "Not injury related…" notes from **both** primary and secondary), and a short practice code
  (DNP/Ltd/Full/Out). Consumed by both `matchups.py` (box score) and `teams.py` (`team_roster`
  joins `injury_reports_for_week`); `BoxPlayer` + `TeamRosterPlayer` schemas gain
  `injury_secondary`/`injury_practice_status` (client regenerated, no drift). Frontend: shared
  `web/src/components/InjuryBadge.tsx` renders `Status · Primary[/Secondary] · PracticeCode` inline
  with a full-sentence tooltip; "Out" practice not repeated behind an "Out" status. Real-DB check
  (2024 wk1): McCaffrey `Q · Calf/Achilles · Ltd`, Marquise Brown `Out · Shoulder · DNP`, Chase's
  "resting player" note suppressed. Tests: new `tests/test_injuries.py` (9, no DB) +
  `InjuryBadge.test.tsx` (5). Full gate green (314 backend / 159 frontend).

**Recently merged (since the 2026-06-08 doc consolidation):**

- **P12 — Player injury reports (BFF + UI) — MERGED, PR #53.** `analytics/matchups.py` joins
  `injury_reports_for_week` and adds `injury_status` / `injury_body_part` per player; `BoxPlayer`
  schema + regenerated client; inline `InjuryBadge` ("Out · Knee", "Q") on the box score; reason
  appended to the "Out" tooltip. P12 is **complete** (Phase 1 table merged upstream first).
- **Box-score enrichment — MERGED, PR #52 + #53.** IR/RES split out from bench in the roster
  layout, player game-status display, projections computed from raw stats, column-header tooltips.
- **Commissioner history — MERGED (#54-line / #56 to main).** Upstream `commissioners` table +
  seed/loader and `queries.commissioner_terms`; `analytics/commissioners.commissioner_history`;
  `CommissionerTerm` on `LeagueOverview` + `OwnerCareer`; commissioner strip on `/league`,
  per-season badge, and a manager-profile card. Succession: harry → sully → scott → Dave → Jeff →
  Chris → DJ → Rob (2024–present).
- **Playoffs/Bracket — shipped, MERGED, PRs #55 + #60.** F2.3 evolved from the caveated `/bracket`
  endpoint into a true bracket visualization (#55) and then split into separate **championship**
  and **consolation** brackets (#60). N2 is now **shipped**, not just "resolved locally."
- **Seasons / Rules & Eras page redesign — MERGED, PRs #54 + #59.** `/seasons/` timeline rebuilt
  with an impact hierarchy and before→after diffs; PR #59 resolves headline-only NFL.com setting
  edits into concrete change details instead of bare gaps.
- **F-54 — season-correct player NFL team — MERGED, PR #51.** Dashboard routes `stats.py:season_totals`
  and `teams.py:team_roster` through upstream `queries.player_season_teams` (folds to season-era
  codes; a 2015 Raider reads "OAK"), with a `players.nfl_team` snapshot fallback. No API shape
  change. Real-DB spot check confirmed 2015 renders SD/OAK/STL.
- **Standings 500 fix — MERGED, PR #57.** `conference_id` read via raw SQL because the Phase-1
  `Team` ORM model does not map the column. **This same model drift still breaks the gate** — see
  Open items.
- Earlier merged work (league-history slice, season-aware team names, player zero-week fix,
  records season-correct champion, team avatars Q11, deferred decisions Q10–Q13, fix-passes P1–P6)
  is all archived in `docs/archive/COMPLETED_WORK.md`.

## Next

**The forward execution plan is `docs/plans/COMPLETION_ROADMAP.md`** — handoff-ready sessions
S1–S8 covering everything below. Summary:

- **S1 — repair the silently-dead conferences feature (dashboard, do first).** Gate is already
  green; this is the raw-SQL rewrite that revives the 2010–2019 conference era (see Open items).
- **S2 — ship `feature/rivalries-insights` → `dev`** (packaging).
- **UP program S3–S7 (upstream / `../danger-zone`):** F-49 playoff/consolation metadata, F-27
  reconstructed-scoring trust check, F-25 player-identity residuals, F-37 tier 2 transactions/FAAB,
  and F-06 ownership succession (⊘ blocked — needs a source ledger you supply). Detail in
  `docs/ACTIVE_WORK.md` §2.
- **S8 — league-history expansion (dashboard, last).** Gated on the UP outputs (per-season config
  ledger: scoring tables, schedule length, waiver↔FAAB, playoff format, durable manager overrides).

## Files that matter now

- Rivalries-insights surfaces (open branch): `src/ff_dashboard/analytics/rivalries.py`,
  `src/ff_dashboard/api/routes/rivalries.py`, `web/src/features/rivalries/RivalryInsights.tsx`
- Injury-enrichment surfaces (open branch): `src/ff_dashboard/analytics/injuries.py`,
  `web/src/components/InjuryBadge.tsx` (used by `BoxScorePage.tsx` + `teams/TeamPage.tsx`)
- **Silently-dead conferences feature (S1):** `src/ff_dashboard/analytics/conferences.py`
  (`_CONFERENCE_MODELS_AVAILABLE` is `False` at runtime; also imported by `analytics/bracket.py`
  and routed at `GET /v1/seasons/{id}/conferences`) — gate is green, but the feature still needs
  the raw-SQL rewrite. See Open items.

## Open items / deviations

- **Conferences feature is silently dead (functional, not a gate failure).** The gate-red debt
  this section used to escalate was cleared by `51344a1` (stale matchups-test assertions removed;
  `conferences.py` mypy/ruff silenced via `type: ignore`). But the silencing only fixed the types —
  at runtime `analytics/conferences.py` still imports non-existent Phase-1 ORM models
  (`SeasonConference`, `Team.conference_id`), so `_CONFERENCE_MODELS_AVAILABLE` is `False` (verified
  2026-06-15). The feature is **silently dead for the entire 2010–2019 conference era** — every
  season wrongly returns `no_conferences_this_season`, and `conference_map()` (used by
  `analytics/bracket.py`) returns `{}`. The data is fine: `standings.py` already reads the same
  `teams` / `season_conferences` tables via raw SQL. **Fix:** rewrite `conferences.py` to use the
  same raw SQL. Full handoff: S1 in `docs/plans/COMPLETION_ROADMAP.md`.
- Residual non-blocker from F-53 verification: 1–2 phantom **week-1-only** teams per season with
  duplicate/garbled names, present 2010–2018 and absent 2019/2023/2025. Separate from the repaired
  roster-churn corruption; belongs with owner/team-identity research (F-06).
- League relevance = **ever-rostered only** (not "ever scored"): the pipeline scores the whole
  NFL, so "scored" is not a league-relevance signal.
- F-49 remains upstream: playoff/consolation metadata is insufficient to compute `made_playoffs`
  honestly for every season, so the dashboard returns `None` where the bracket cannot be inferred.

---

## Milestone tracker (P0–P12, from docs/09_ROADMAP.md)

| # | Milestone | Status | Plan | Notes |
|---|-----------|--------|------|-------|
| P0 | Prereqs & data-readiness gate | ☑ | — | data coverage note |
| P1 | BFF bootstrap (`/health`, `/v1/meta`, cache) | ☑ | — | `test_p1_bootstrap.py` |
| P2 | Analytics core + endpoints (standings, owners, h2h, records, players) | ☑ | — | fixture DB + known answers |
| P3 | Frontend bootstrap + design system | ☑ | — | tokens, primitives, gen:api drift check |
| P4 | Home + Standings + Manager profile | ☑ | — | + managers index/profile |
| P5 | Matchups + Box score (optimal lineup) | ☑ | — | authoritative NFL.com points |
| P6 | Rivalries + Records book | ☑ | — | deep-links to source matchup |
| P7 | Players + Stats explorer + Team page | ☑ | — | + players data-honesty audit |
| P8 | Draft views | ☑ | — | gap-label seasons w/o drafts |
| P9 | Power ranking + timelines | ☑ | — | shared chart wrappers |
| P10 | Global search + coverage/about + gap polish | ☑ | — | no fake zeros anywhere |
| P11 | Operations + docs + e2e/visual-regression | ☑ | — | Makefile/RUNBOOK/e2e + visual baselines in CI |
| P12 | Player injury reports (Phase 1 + BFF + UI) | ☑ | — | Phase 1 upstream + Phase 2 BFF/UI merged (PR #53) |

Status key: ☐ todo · ◐ in progress · ☑ done. Put the plan path in **Plan** once a PLAN
session writes `docs/plans/P{N}-{name}.md`.
