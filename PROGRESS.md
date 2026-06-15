# PROGRESS.md — dz-dashboard (Phase 2)

The single source of truth for "where we are." **Read this first every session** instead of
re-scanning `analytics/` and `web/`. Keep it short and current — update it at every checkpoint
and at the end of every milestone. This file is what makes the plan/build/verify split cheap.

How to use it (see `CLAUDE.md` + `.claude/skills/milestone-session`):
- At session start, read this, then the one `P{N}` row in `docs/09_ROADMAP.md`, then the plan
  (`docs/plans/P{N}-*.md`) if one exists. Stop there — don't browse the tree.
- At session end / checkpoint, update **Current state**, **Next**, and **Open items**.
- Aggregated history lives in `docs/archive/COMPLETED_WORK.md` (done) and `CHANGELOG.md`
  (reverse-chron passes); all remaining/open scope lives in `docs/ACTIVE_WORK.md`.

---

## Current state

**The dashboard application is functionally complete and fully merged.** All P0–P12 milestones,
all P1–P6 review fix-passes, and every post-roadmap product slice are merged to `dev` and promoted
to `main`. As of 2026-06-15 there are **no open feature branches** — the branches that recent docs
described as "awaiting PR" all landed:

- **#61** rivalries-insights — five league-wide rivalry insight bands + `GET /v1/rivalries/insights`.
- **#62** seasons league-changes — full auditable classifier (`analytics/league_changes.py`),
  nothing dropped; 3-tier Rules & Eras display.
- **#63 / #64** baseline gate debt — stale matchups tests removed, conferences `mypy`/`ruff`
  silenced, e2e + format debt cleared. **Gate is green.** (See Open items: the conferences
  *feature* is still silently dead at runtime even though its types are silenced.)
- **#65** injury enrichment — shared `analytics/injuries.py`; `InjuryBadge` on box score + roster.
- **#66** engagement / rivalries-strength — Standings "Robbed & Blessed" callouts + Manager-profile
  "Your Story" band (`analytics/owner_story.py`). The per-manager epithet proposal was presented
  but **not retained** (12/12 managers earned one → failed the "earned, not noisy" bar).
- **#67** matchup zero-status — team-roster scoring shares box-score zero semantics; read-only audit
  helper `scripts/audit_zero_score_gaps.py`; live run found 0 unexpected zeroes / 0 missing DST rows.

The aggregate of all finished work is `docs/archive/COMPLETED_WORK.md`; the remaining open scope is
`docs/ACTIVE_WORK.md`.

## Next

All remaining work is tracked in **`docs/ACTIVE_WORK.md`**. In priority order:

1. **Repair the silently-dead conferences feature** (dashboard, do first; see Open items). The gate
   is green but `analytics/conferences.py` returns empty for the entire 2010–2019 conference era.
   Fix = the raw-SQL rewrite `standings.py` already uses. `docs/ACTIVE_WORK.md` §6.1.
2. **The UP (upstream / `../danger-zone`) program** — Phase-1 data/research, not dashboard PRs:
   F-49 playoff/consolation metadata, F-27 reconstructed-scoring trust check, F-25 player-identity
   residuals, F-37 FAAB, and F-06 ownership succession (⊘ blocked — needs a source ledger you
   supply). `docs/ACTIVE_WORK.md` §2.
3. **League-history expansion** (dashboard, last) — gated on the UP outputs (per-season config
   ledger). `docs/ACTIVE_WORK.md` §3.

## Open items / deviations

- **Conferences feature is silently dead (functional, not a gate failure).** `analytics/conferences.py`
  still imports non-existent Phase-1 ORM models (`SeasonConference`, `Team.conference_id`), so
  `_CONFERENCE_MODELS_AVAILABLE` is `False` at runtime (verified 2026-06-15). Every season wrongly
  returns `no_conferences_this_season` and `conference_map()` (used by `analytics/bracket.py`)
  returns `{}` — the 2010–2019 conference era is invisible. The data is fine: `standings.py` already
  reads the same `teams` / `season_conferences` tables via raw SQL. **Fix:** rewrite
  `conferences.py` to use the same raw SQL. Full handoff: `docs/ACTIVE_WORK.md` §6.1.
- **Phantom week-1-only teams (identity artifact).** 1–2 phantom week-1-only teams per season with
  duplicate/garbled names, present 2010–2018 and absent 2019/2023/2025. Separate from the repaired
  F-53 roster-churn corruption; belongs with owner/team-identity research (F-06).
- **F-49 `made_playoffs = None`** where a bracket can't be inferred honestly — intentional until
  upstream playoff/consolation metadata lands (see `docs/ACTIVE_WORK.md` §2 F-49).
- **League relevance = ever-rostered only** (not "ever scored"): the pipeline scores the whole NFL,
  so "scored" is not a league-relevance signal.

---

## Milestone tracker (P0–P12, from docs/09_ROADMAP.md)

| # | Milestone | Status | Notes |
|---|-----------|--------|-------|
| P0 | Prereqs & data-readiness gate | ☑ | data coverage note (`docs/03_DATA_ACCESS.md`) |
| P1 | BFF bootstrap (`/health`, `/v1/meta`, cache) | ☑ | `test_p1_bootstrap.py` |
| P2 | Analytics core + endpoints (standings, owners, h2h, records, players) | ☑ | fixture DB + known answers |
| P3 | Frontend bootstrap + design system | ☑ | tokens, primitives, gen:api drift check |
| P4 | Home + Standings + Manager profile | ☑ | + managers index/profile |
| P5 | Matchups + Box score (optimal lineup) | ☑ | authoritative NFL.com points |
| P6 | Rivalries + Records book | ☑ | deep-links to source matchup |
| P7 | Players + Stats explorer + Team page | ☑ | + players data-honesty audit |
| P8 | Draft views | ☑ | gap-label seasons w/o drafts |
| P9 | Power ranking + timelines | ☑ | shared chart wrappers |
| P10 | Global search + coverage/about + gap polish | ☑ | no fake zeros anywhere |
| P11 | Operations + docs + e2e/visual-regression | ☑ | Makefile/RUNBOOK/e2e + visual baselines in CI |
| P12 | Player injury reports (Phase 1 + BFF + UI) | ☑ | Phase-1 upstream + BFF/UI merged (PR #53) |

Status key: ☐ todo · ◐ in progress · ☑ done.
