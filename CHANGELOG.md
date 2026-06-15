# CHANGELOG.md — dz-dashboard

Reverse-chronological history for completed passes, audits, and notable data-regeneration events.
Keep `PROGRESS.md` focused on current state. For the consolidated, fully-organized records see
`docs/archive/COMPLETED_WORK.md` (all finished work) and `docs/ACTIVE_WORK.md` (all remaining work).

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
