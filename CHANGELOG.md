# CHANGELOG.md — dz-dashboard

Reverse-chronological history for completed passes, audits, and notable data-regeneration events.
Keep `PROGRESS.md` focused on current state.

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
