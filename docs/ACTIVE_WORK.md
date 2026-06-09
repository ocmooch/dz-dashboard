# ACTIVE_WORK.md — dz-dashboard (active aggregate)

The consolidated, **non-archived** record of everything not yet done: remaining tasks,
in-progress work, blockers, open decisions, the upstream program, and deferred enhancements.
This is the **forward-looking** companion to `docs/archive/COMPLETED_WORK.md` (finished work).

Read order at session start stays: `PROGRESS.md` → the relevant `docs/09_ROADMAP.md` row /
`docs/plans/REVIEW_FIXES_ROADMAP.md` → this file for the open scope.

Status key: ☐ todo · ◐ in progress · ⊘ blocked (needs an input/decision) · ⤴ upstream (out of
this repo, in `../danger-zone` / ff-pipeline).

---

## 0. At-a-glance — what is actually open

The dashboard application is functionally complete (all P0–P11 milestones and all P1–P6 review
fix-passes are merged — see the archive). The remaining work is, in priority order:

1. **Packaging the current feature branch** for review/PR (`feature/season-aware-team-names`). ◐
2. **The UP (upstream / danger-zone) program** — Phase-1 data/research, not dashboard PRs. ⤴
3. **League-history expansion** once upstream identity/rules data exists. ☐
4. **Deferred product decisions** (theme toggle, avatars, exports, etc.) — reversible defaults. ☐
5. **Housekeeping** (the `pyproject.toml` fallback-tag bump). ☐

---

## 1. In-progress / immediate — current feature branch ◐

**Branch:** `feature/season-aware-team-names` (latest commit `67acb5b` — league-history slice,
season-aware names, zero-week player fix; all landed locally, see archive §3).

- ◐ **Review / PR packaging.** The league-history slice, season-aware team names, and the
  player zero-week fix are implemented and locally verified but not yet packaged into a reviewed
  PR to `dev`. Next dashboard step is the review/PR for this branch.
- ☐ **Run the full green gate** before PR (backend pytest + ruff + mypy; frontend gen:api
  no-drift + typecheck + Vitest; e2e where relevant) and complete a real-DB click-through of the
  new league/Seasons/Stories/About-Data surfaces.
- **Files that matter for this branch:**
  - F2.3 bracket: `src/ff_dashboard/analytics/bracket.py`,
    `src/ff_dashboard/api/routes/seasons.py`, `web/src/features/bracket/BracketPage.tsx`
  - League-history: `src/ff_dashboard/analytics/league_history.py`,
    `src/ff_dashboard/api/routes/league.py`, `web/src/features/league/`
  - Player zero-week: `src/ff_dashboard/analytics/players.py`,
    `src/ff_dashboard/api/schemas.py`, `web/src/features/players/PlayerDetailPage.tsx`
  - Docs touched for packaging: `docs/03_DATA_ACCESS.md`, `docs/04_ANALYTICS_MODEL.md`,
    `docs/05_API_CONTRACT.md`, `docs/07_PAGES_AND_VIEWS.md`, `docs/09_ROADMAP.md`,
    `docs/10_OPEN_QUESTIONS.md`, `PROGRESS.md`

---

## 2. The UP program — upstream / danger-zone (Phase-1 data & research) ⤴

These are **not dashboard PRs.** They live in `../danger-zone` (ff-pipeline). Each, when it
lands, retires one or more dashboard findings without a dashboard code change (read-only
boundary). Detailed log: `docs/plans/REVIEW_FIXES_ROADMAP.md`; per-program handoff:
`docs/handoffs/players-audit-danger-zone.md`. Status reflects the 2026-06-07 read-only spot check.

### F-06 — Ownership-succession history ☐ ⊘ (needs a source)
A human/source ledger of which owner held which team across which seasons. There are 12
persistent teams but >12 owners over time; owner ≠ team and tenures vary. **Blocked on a
source/table.** Should precede any schema or manager-record reinterpretation.
(See memory `owner-vs-team-identity`.)

### F-25 — Residual player-identity cleanup ◐ ⤴ (improved, not closed)
Rerun the player-audit queries in `docs/handoffs/players-audit-danger-zone.md` (use the
status-update counts, not the original counts), then fix or document the residuals upstream.
Current real-DB residual (3048 players):
- D1 `last_season IS NULL` = 277 (was 100%); largely improved, still open.
- D2 league-rostered `rookie_year IS NULL` = 38; open.
- D4 never-rostered / never-scored "ghost" players = 400; scope-policy decision still open.
- D5 duplicate same-player/season/week roster rows = **0** → effectively resolved.
- D3 `is_active` semantics + stale `nfl_team` — needs a documented, stable definition.
- Coordinated API addition: expose `last_season` on `PlayerOut` once D1 is fully populated
  (additive; run dashboard `gen:api` drift check in the same cycle).
Remaining nulls/ghosts must be either fixed or documented as **true source gaps**.
(See memory `player-stub-duplicates`.)

### F-27 — Trust check on reconstructed pre-2016 scoring ◐ ⤴ (data landed; validation open)
The data half is ☑ (F-51: `player_stats_scored` spans 2010–2025). **Still open:** sanity-check
representative weeks, outliers, and season totals for 2010–2015 against source NFL.com / team
totals before treating every reconstructed score as authoritative.

### F-37 tier 2 — Exact transactions & FAAB ◐ ⤴ (partly landed)
Upstream now has dated, typed transaction rows (add/drop/waiver/free-agent/trade/draft/lineup),
and the dashboard renders the derived roster-diff tier. **Open:** the dashboard has not yet
consumed exact transaction dates/types as a richer tier, and **no FAAB bid rows were present** in
the spot check. Determine whether historical FAAB bid amounts exist anywhere; if absent, document
`faab_bid:null` as a true source gap. The waiver standard-order → FAAB switch point is still
unresolved.

### F-49 — Playoff / consolation metadata ☐ ⤴
`Matchup.is_consolation` is `0` for all playoff rows and `is_playoff` is set on every
post-season game, so all 12 teams look like they advanced each season. The dashboard therefore
returns `made_playoffs = None` unless a season's bracket is a proper subset of the league
(a few older seasons qualify), and the `/bracket` view stays caveated. **Fix source-derived
`is_consolation` / playoff-team metadata in ff-pipeline** (prefer fixing source flags over
dashboard inference); `made_playoffs` then resolves with no contract change.

### Resolved-upstream (no longer open) — for reference
F-50, F-51, F-52, F-53 are all ☑ via the regen — see `docs/archive/COMPLETED_WORK.md` §5.

---

## 3. League-history expansion (next product slice) ☐

The league-history slice is landed (archive §3). Its next expansion should **consume
upstream/manual identity and rules data when available**:
- durable human manager overrides (depends on F-06);
- roster-slot settings; full scoring-rule tables; playoff-format metadata (depends on F-49);
- verified scoring-mismatch classification (depends on F-27).

Per-season config ledger is needed: scoring rules, season length (1–13 → 1–14), waiver → FAAB,
and ownership all changed over time. Switch-years are TBD. (See memories
`league-settings-ledger`, `owner-vs-team-identity`.)

---

## 4. Open product decisions — deferred at defaults (reversible) ☐

From `docs/10_OPEN_QUESTIONS.md`. All shipped at a sensible default and remain reversible.

| # | Decision | As-built default | Open? |
|---|----------|------------------|-------|
| Q8 | Keep-alive / run model | one-command (`make serve`); auto-start options provided but not installed | settled at default |
| Q9 | Caching aggressiveness | in-process only, keyed on `latest_pipeline_run_id`; no materialized table | open only if first-hit latency bites |
| Q10 | Theme toggle | dark-only; `tokens.css` ready for a light set but no `[data-theme="light"]` / UI toggle | **open** if a visible switch is wanted |
| Q11 | Avatars / logos / photos | monogram chips from names; no avatar config | **open** as an enhancement |
| Q12 | Mobile priority | laptop-first responsive | open if phone-first becomes primary |
| Q13 | Exports / sharing | none | **open** as a cheap later add (copy chart as image / CSV) |

---

## 5. Open items / deviations & known non-blockers

- **Phantom week-1-only teams (identity artifact).** 1–2 phantom week-1-only teams per season
  with duplicate/garbled names (e.g. "JFCFPWCPGAWWLTDOSGT", "Rev Russell's Sunday Service"),
  ~2 matchups each, present 2010–2018 and absent 2019/2023/2025. **Separate** from the repaired
  F-53 roster-churn corruption; belongs with the owner/team-identity research (F-06). Worth a new
  finding if it surfaces in the UI.
- **League relevance = ever-rostered only** (not "ever scored"): the pipeline scores the whole
  NFL, so "scored" is not a league-relevance signal. Keep filters on roster presence.
- **F-49 `made_playoffs = None`** where a bracket can't be inferred honestly — intentional until
  upstream metadata lands (see §2 F-49).

---

## 6. Housekeeping ☐

- **`pyproject.toml` git-fallback tag.** Still pinned to `v1.0.0`; a future non-docs pass should
  bump the fallback to a release matching the live ≥1.2.0 avatar-column schema. (Deferred from the
  2026-06-06 docs refresh.)

---

## 7. Questions to revisit at end of Phase 2 (before Phase 3)

From `docs/10_OPEN_QUESTIONS.md` — input-gathering, not blocking work:

- Which views did you actually use? Which planned ones went untouched?
- Did any analytics metric need a definition change once seen on real data?
- Is the in-process cache adequate, or do the big rollups want precomputation?
- Did the BFF stay a thin analytics layer, or is it creeping toward logic Phase 3 should own?
- What new views did you wish for while using it (the most valuable Phase-3 scope input)?

---

## Source docs feeding this aggregate

- `PROGRESS.md` — current-state snapshot (Current state / Next / Files that matter now)
- `docs/plans/REVIEW_FIXES_ROADMAP.md` — detailed append-only build log + UP tracking
- `docs/10_OPEN_QUESTIONS.md` — deferred questions & build-surfaced issues (N5)
- `docs/handoffs/players-audit-danger-zone.md` — the F-25 upstream handoff (D1–D5)
- `docs/handoffs/review-fix-pass.template.md` — manual fix-pass workflow fallback
- `docs/reviews/2026-06-in-browser-review.md` — the 48-finding review (F-01–F-48)
