# Plan — Deferred product decisions (Q10–Q13)

Decisions taken 2026-06-08 by ocmooch on the four genuinely-open deferred product
questions from `docs/10_OPEN_QUESTIONS.md` (§Deferred) / `docs/ACTIVE_WORK.md` §4.
This plan records the three that close at their default and lays out the one build
(Q11 — team avatars from the DB).

| # | Decision | Call | Work |
|---|----------|------|------|
| Q10 | Theme toggle | **Keep dark-only** | Doc-close only |
| Q11 | Avatars / logos / photos | **Pull from DB if present**, monogram fallback | **Build** (below) |
| Q12 | Mobile priority | **Keep laptop-first** | Doc-close only |
| Q13 | Exports / sharing | **None** | Doc-close only |

---

## A. Doc-closures (Q10, Q12, Q13) — no code

Flip these from "**open**" to settled in both source docs, preserving rationale so the
choice can be revisited later.

- `docs/10_OPEN_QUESTIONS.md`
  - **Q10** — change "**Still open** if you want a visible switch" → "**Settled
    2026-06-08: keep dark-only.** `tokens.css` remains structured for a light set if ever
    wanted; no `[data-theme="light"]` and no toggle by deliberate choice."
  - **Q12** — already at default; add "**Settled 2026-06-08: keep laptop-first.**"
  - **Q13** — change "**Still open** as a later add" → "**Settled 2026-06-08: no exports.**
    Localhost single-user; revisit only if league-chat sharing becomes a real need."
- `docs/ACTIVE_WORK.md` §4 table — set Q10/Q12/Q13 "Open?" cells to "settled 2026-06-08";
  set Q11 to "in progress — see `docs/plans/deferred-product-decisions.md`".

**Done when:** both docs read as settled for Q10/Q12/Q13; no "**open**" bold remains on them.

---

## B. Build — Q11 team avatars from the DB

> **As built (2026-06-08) — deviation from step 4 below.** During the build, `TeamRef` turned
> out **not** to be the surface the chips consume — every page feeds `<Chip>` from per-row fields
> (`StandingRow`, `PowerRow`, `BracketTeam`, …), each already carrying `team_id`. Rather than add
> `team_avatar_url` to ~8 schemas and churn the generated client, the endpoint is **team-keyed**:
> `GET /v1/teams/{team_id}/avatar` (binary, `include_in_schema=False`). The frontend builds the URL
> from `team_id` via `teamAvatarUrl()` and relies on `<img onError>` → monogram for the no-avatar /
> 404 case. **No JSON-schema change, no `gen:api` drift.** `assets_root` is injected on `app.state`
> (like `engine`/`cache`) so tests point it at a temp store. Everything else below holds.

### What the data actually supports (verified on the real DB, 2026-06-08)

- `teams.team_avatar_asset_id` populated on **190** per-season team rows;
  `teams.owner_avatar_asset_id` populated on **0**.
  → **Team logos exist; owner/manager photos do not.** Managers stay on monograms and we
  record owner avatars as a **true source gap** (would depend on an upstream backfill).
- Avatars are **per-season snapshots** on the per-season `teams` row (matches `TeamRef.team_id`).
- Bytes are **content-addressed on disk**, not in SQLite: `assets.storage_path` is relative
  (e.g. `51/51fad…png`) under the danger-zone asset store
  `../danger-zone/data/assets/`. DB holds only metadata (`sha256`, `content_type`,
  `byte_size`, `storage_path`). 171 asset rows, deduped by `sha256`.
- Caveat: one row has `content_type=image/jpeg` with a `.png` path — trust `storage_path`
  bytes; send `content_type` from the column but don't assert on the extension.

### Boundary check

Read-only and within the seam: we read `ff_pipeline.repository` metadata and stream bytes
from the Phase-1 asset store on disk. No DB writes, no Phase-1 logic. New file reads need a
configurable asset-store root.

### Steps

1. **Setting — asset store root.**
   `src/ff_dashboard/settings.py`: add `assets_root: Path | None = None` (env `ASSETS_ROOT`).
   Default it next to the resolved SQLite DB: `<db_dir>/assets`. Add a `resolved_assets_root()`
   like `resolved_database_url()`. Document in `.env.example` if one exists.

2. **Read-only query helper.**
   Prefer adding to `ff_pipeline/repository/queries.py` (additive, read-only) a helper that,
   given an `asset_id`, returns `(storage_path, content_type, byte_size)`; and one that maps a
   per-season `team_id` → `team_avatar_asset_id`. If editing Phase 1 is undesirable this cycle,
   read the two columns via the existing repository session in a dashboard-side data function
   under `analytics/` (no math; pure lookup). Choose the queries.py route if it's a clean
   additive helper; otherwise keep it dashboard-side.

3. **Asset-serving endpoint.**
   New `src/ff_dashboard/api/routes/assets.py`: `GET /v1/assets/{asset_id}`.
   - Look up the asset row; 404 if missing.
   - Resolve `resolved_assets_root() / storage_path`; 404 if the file is absent (graceful — the
     UI must fall back to monogram, never error the page).
   - Guard against path traversal (reject `storage_path` containing `..` or absolute paths;
     resolve and assert the final path is inside the assets root).
   - Stream with `FileResponse`, `media_type=content_type or "application/octet-stream"`,
     and a long-lived immutable `Cache-Control` (content-addressed ⇒ safe to cache hard).
   - Register the router in the app the same way the others are.

4. **Schema surfacing.**
   `src/ff_dashboard/api/schemas.py`: add `team_avatar_url: str | None = None` to **`TeamRef`**
   (the shared team reference most chips consume). Populate it in the routes that build
   `TeamRef` (standings, power, matchups, team overview) as
   `f"/v1/assets/{team_avatar_asset_id}"` when the id is non-null, else `None`.
   Do **not** add an owner avatar field — no data; documented gap.
   Keep it additive/optional so unrelated payloads are unaffected.

5. **Regenerate the client + drift check.**
   `cd web && npm run gen:api && git diff --exit-code web/src/lib/api` (expect the new optional
   `team_avatar_url` in `schema.d.ts`). Never hand-edit the generated client.

6. **Chip component.**
   `web/src/design-system/index.tsx` — extend `Chip` to accept optional
   `avatarUrl?: string | null`. When present, render `<img className="dz-avatar" src={avatarUrl}
   alt="" loading="lazy" onError={…fall back to initials}/>`; otherwise the existing
   `initials(name)` monogram. The monogram stays the universal fallback (null url, 404, or load
   error). Add the matching `dz-avatar` `<img>` styling in `global.css` (object-fit: cover,
   same size/round as the monogram so layout is unchanged).
   Thread `avatarUrl={team.team_avatar_url}` from the call sites that render team chips
   (standings, power, matchups, team page, home). Manager/owner chips pass nothing → monogram.

7. **Tests.**
   - Backend: a route test for `/v1/assets/{id}` — happy path streams bytes + content_type;
     missing asset → 404; missing file on disk → 404; traversal attempt → rejected. Add a tiny
     fixture asset (bytes + row) to the fixture DB/asset dir.
     A schema/route test asserting `team_avatar_url` is set when the asset id is present and
     `None` when absent.
   - Frontend: a `Chip` test — renders `<img>` with `avatarUrl`, renders monogram when null,
     and falls back to monogram on `<img>` error.

8. **Docs.**
   - `docs/05_API_CONTRACT.md` — document `GET /v1/assets/{asset_id}` and the `team_avatar_url`
     field.
   - `docs/03_DATA_ACCESS.md` — note the asset-store-on-disk read path + `ASSETS_ROOT` setting,
     and record **owner avatars as a true source gap** (0 rows populated).
   - `docs/ACTIVE_WORK.md` §4 — mark Q11 done; cross-link the owner-avatar gap to the F-06
     ownership-succession / upstream program.

### Done when

- `GET /v1/assets/{id}` serves a team logo from the danger-zone asset store, 404s cleanly when
  the asset/file is missing, and rejects traversal.
- `team_avatar_url` rides on `TeamRef`; the client is regenerated with no manual edits and the
  drift check passes.
- Team chips show the logo where one exists and the monogram everywhere else (null/404/error);
  manager chips stay monograms.
- Full green gate passes (backend pytest+ruff+mypy; frontend gen:api no-drift + typecheck +
  lint + Vitest), and a real-DB click-through shows real team logos with monogram fallback.
- Docs updated; committed with the trailer format.

### Out of scope / noted gaps

- **Owner/manager photos** — no DB data; not built. Documented gap, depends on an upstream
  backfill (relate to F-06).
- Avatar upload/local-override config — not needed; DB is the source per the decision.

---

## Sequencing

1. Do **A (doc-closures)** immediately — trivial, closes three decisions.
2. Run **B** as its own small build (PLAN already captured here → BUILD → VERIFY), ideally
   after the current `feature/season-aware-team-names` branch is packaged/merged, on a fresh
   `feature/team-avatars` branch off `dev`.
