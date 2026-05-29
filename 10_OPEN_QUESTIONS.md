# 10 — Open Questions & Default Decisions

Read this **early**. The rest of the package assumes the answers below. Each is reversible,
but several change a lot downstream, so confirm or redirect before build starts. Items are
grouped: **decisions needing your sign-off** first, then **deferred-to-implementation**
questions, then **locked-in** choices.

---

## Decisions needing your sign-off

### Q1. Data-access architecture: BFF reusing the repository (RECOMMENDED) vs browser-only

**Default (recommended):** a Phase 2 backend-for-frontend (`ff_dashboard`) that imports
`ff_pipeline.repository` and reads the SQLite file directly; all analytics computed
server-side; the frontend is pure presentation calling only the BFF.

**Alternative:** no new backend — the React app calls the Phase 1 read API directly and does
all aggregation in the browser.

| | BFF (recommended) | Browser-only |
|---|---|---|
| Aggregation over 180k rows | one SQL query | dozens of paginated calls |
| Business logic location | tested Python, one place | TypeScript, duplicated, harder to test |
| Contract | generated, build-time enforced | hand-managed |
| New backend to maintain | yes (small, same stack) | no |
| Honors Phase 1 "analytics = Phase 2" | yes | strains it |

**Recommendation: BFF.** The only real cost is a second small Python service in the same
repo, sharing all of Phase 1's tooling. Confirm this; everything in docs 02/03/05 assumes it.

### Q2. Frontend stack

**Default:** React 18 + TypeScript + Vite + Tailwind + (hand-built primitives, optionally
seeded from shadcn/ui) + TanStack Query + React Router + Recharts + openapi-typescript.

Open to swap any piece. Most likely alternatives to consider: **SvelteKit** (lighter, but
smaller charting ecosystem and you'd not reuse Phase 1 React knowledge), **Next.js** (heavier;
SSR unneeded for a localhost single-user SPA), **visx/nivo** instead of Recharts (more
control, more code). Confirm the stack or name swaps.

### Q3. Visual direction: "Danger Zone" HUD (PROPOSED)

**Default:** dark, instrument-panel aesthetic with afterburner-orange accent, mono/tabular
numerics, HUD-style charts (see `06_DESIGN_SYSTEM.md`). It's distinctive and ties to the
league identity, and it's fully token-driven so it can be re-skinned.

**Alternatives:** a cleaner Sleeper-like neutral dark; a light editorial look; a retro
"Madden/ESPN broadcast" theme. Tell me if you want a different direction or a light default —
the components don't change, only the tokens.

### Q4. Which views ship first / what's most valuable to you

**Default priority (from `07`/`09`):** Home → Standings → Manager profile → Box score →
Rivalries → Records book → Players/Stats/Team → Draft → timelines → search/polish.

If your actual day-one use is, say, "settle arguments about all-time records and rivalries,"
we can pull Rivalries + Records book earlier (they need only already-solid data). Rank these
or confirm the default.

### Q5. Standings tiebreaker

The standings rank in `04_ANALYTICS_MODEL.md` defaults to **wins, then points-for**. NFL.com
leagues sometimes use head-to-head or other tiebreaks. Confirm your league's actual tiebreak
order so historical standings match NFL.com exactly (this also affects the records book).

### Q6. Power-ranking model

**Default:** transparent z-score blend (50% PPG, 30% win%, 20% last-3-PPG). Confirm the
weights, or tell me to keep it even simpler (pure PPG) — this is intentionally *not* a
prediction model (that's Phase 3).

### Q7. Optimal-lineup definition (for "points left on the bench")

Requires the league's exact starting-slot configuration (QB/RB/WR/TE/FLEX/K/DEF counts, and
what FLEX accepts). **Default:** read it from Phase 1's roster/scoring config if present;
otherwise I'll need you to specify the lineup slots once. Confirm where the slot config lives.

---

## Deferred to implementation

### Q8. Keep-alive / run model for daily use

`make dev` for development is clear. For daily use, do you want the BFF + built frontend
launched on login (cron `@reboot` / a user service, mirroring Phase 1's cookie-era ops), or
are you fine running one command when you want it? **Default:** one command now; document the
auto-start option.

### Q9. Caching aggressiveness

**Default:** in-process memoization keyed on `pipeline_run_id`. If the heaviest rollups
(rivalry matrix, records over 16 seasons) feel slow on first hit, we can precompute them into
a small materialized cache table on pipeline completion. **Default:** in-process only; revisit
if first-hit latency is noticeable.

### Q10. Theme toggle

**Default:** dark-first, with a light theme implemented behind the token system but not
necessarily exposed in the UI initially. Want a visible light/dark toggle on day one?

### Q11. Avatars / team logos / manager photos

Sleeper-style chips look best with avatars. Phase 1 may not store these. **Default:**
initials/monogram chips generated from names; optional later enhancement to let you drop in
manager avatars via a small local config. Confirm if you want avatars early.

### Q12. Mobile priority

**Default:** laptop-first, responsive down to phone (usable, not pixel-perfect). If you'll
mostly check it on a phone, we raise mobile to a first-class target and adjust layouts/charts
accordingly.

### Q13. Exports / sharing

**Default:** none in Phase 2 (it's localhost, single-user). A "copy chart as image" or "export
table as CSV" affordance is a cheap later add if you want to share records in the league chat.

---

## Locked-in (inherited from Phase 1; not re-litigated)

- **SQLite as the data source**, read-only, with the documented Postgres path.
- **Python 3.11+, uv, ruff, mypy --strict, pytest, structlog** for the backend; same
  green-gate-before-merge discipline.
- **Same git model** (`feature/*` → `dev` → `main`) and **AI commit trailers**
  (`AI-Model` / `Prompted-By` / `Reviewed-By`; never `Co-Authored-By: Claude`).
- **No writes, no predictions, no pipeline control from the UI, localhost-only.**
- **Honesty about data gaps is non-negotiable** — unscored 2010–2015, current-season-only
  availability, and incomplete DST scoring are surfaced, never faked.

---

## Questions to revisit at the end of Phase 2 (before Phase 3)

- Which views did you actually use? Which planned ones went untouched?
- Did any analytics metric need a definition change once you saw it on real data?
- Is the in-process cache adequate, or do the big rollups want precomputation?
- Did the BFF stay a thin analytics layer, or is it creeping toward logic Phase 3 should own?
- What new views did you wish for while using it (the most valuable input for Phase 3 scope)?
