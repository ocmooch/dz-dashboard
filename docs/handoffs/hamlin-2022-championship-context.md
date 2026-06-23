# Handoff → dz-dashboard: 2022 championship "Damar Hamlin" display context

**Repo:** `/home/mainuser/dz-dashboard`  ·  **Depends on:** the upstream fix landing first —
`danger-zone/docs/handoffs/hamlin-2022-no-contest-resolution.md`.

## Context

The 2022 NFL Week 17 Bills@Bengals game was suspended after Damar Hamlin's cardiac arrest and
ruled a **no-contest** — never replayed. Our league resolved it by, for each affected BUF/CIN
player, taking **their Week-17 stats accrued before play stopped PLUS their NFL Week-19 (Wild Card)
game** (`final = wk17_partial + wk19`; Week 18 skipped). The **upstream** handoff corrects the data
(champion, ranks, matchup scores, per-slot points) and writes a provenance flag. This dashboard work
is **display only** — render the corrected scores, explain the unusual context, and add a curated
timeline event. The dashboard is read-only and does **no** metric math.

After the upstream fix the title game reads **Smokin Doubs (165) def. CMC (160)** (≈139 vs ≈101 once
partials are included), and `records.championships()` (`analytics/records.py:334`, reads
`Season.champion_team_id`) + `routes/seasons.py:list_seasons()` show Doubs as 2022 champion
automatically. The remaining work is context, honest per-player labelling, and the timeline event.

## Provenance contract (set upstream, read here — do not diverge)

Each affected `team_rosters` slot for `season_year=2022, week=17` carries:
```json
"extra_data": {
  "nfl_com_points": 26.8,
  "hamlin_substitute": {
    "basis": "no_contest_wk17partial_plus_wk19",
    "league_points": 26.8,
    "wk17_partial": { "raw_stats": {...}, "points": 5.54 },
    "wk19":         { "raw_stats": {...}, "points": 21.26 },
    "points_breakdown": {...combined...}
  }
}
```
`league_points` = `wk17_partial.points + wk19.points`. Because `nfl_com_points` already holds that
sum, `_authoritative_points` (`analytics/matchups.py:103`) reaches the corrected team total with no
change. Key all dashboard affordances off the presence of `hamlin_substitute`.

## Work items

### 1 — Box-score context (`analytics/matchups.py`)
- In `box_score()` (~888) / `_team_box()` (~649), when a slot has `hamlin_substitute`:
  - emit its `points_breakdown` so passing yards / receptions / FGs render (the user explicitly
    wants stat-level fidelity, not just a total). Ideally expose the **two components**
    (`wk17_partial` + `wk19`) so the breakdown shows the cancelled-game partial and the Wild Card
    add-on separately;
  - set a per-player `context_label` like **"Wk17+19"** + `context_detail` "Game cancelled (Hamlin
    no-contest); league counted Week-17 partial + the Wild Card week (Week 18 skipped)";
  - **suppress the false `classify_zero()` paths** (`matchups.py:437–468`) for these slots —
    `did_not_play` / `unexpected` would misfire now that `league_points>0` but Week-17 nflverse is
    absent. Branch on the provenance flag *before* `classify_zero`.
- Add a matchup-level **resolution banner** string summarizing the no-contest + the
  Week-17-partial-plus-Week-19 ruling, and show it on **every** week-17 2022 matchup that contains an
  affected player — not only the title game. Drive this purely off the presence of
  `hamlin_substitute` on any slot in the matchup (do not hardcode matchup ids). All six 2022
  final-round placement games contain an affected player; the meaningful ones the user flagged map
  (via `analytics/bracket.py` `season_bracket()` labels) to **Championship = m2635, 3rd Place =
  m2643, 7th Place / consolation-winner = m2637, 11th Place = m2641** — but the caveat appears
  wherever an affected player is rostered, not only these. The banner text should make clear the
  scores come from **public data** (Wk17 partial play-by-play + Wk19), and that a recovered private
  league note was corroboration only and incomplete.

### 2 — Schema (`api/schemas.py`) + client regen
- Add optional `resolution_note: str | None = None` to `BoxScore` (~430–460).
- Add a substitution context block to `BoxPlayer` (reuse `context_label`/`context_detail`; optionally
  expose the `wk17_partial` / `wk19` component points so the UI can show the split); the combined
  breakdown rides on existing `points_breakdown`.
- Run `npm run gen:api && git diff --exit-code web/src/lib/api`. **Never** hand-edit the generated client.

### 3 — Curated timeline event (new affordance)
The timeline is built only from `setting_change` transactions + derived state
(`analytics/league_changes.py`, `analytics/league_history.py`); a narrative NFL event has no
transaction, so add a small **curated narrative-events** source:
- new `analytics/curated_events.py` returning `LeagueChangeDetail`-shaped events
  (`schemas.py:394–414`): `category="league_event"`, `tier="T1"`, `source="league_ruling"`,
  `certainty="verified"`, dated, summary covering the Hamlin no-contest, the
  Week-17-partial-plus-Week-19 substitution rule (Week 18 skipped), and its championship effect
  (Doubs over CMC). Ground the summary in **public record** — cite the NFL no-contest ruling
  (NFL.com/ESPN) and that the substitute scores are verifiable public stats (Wk17 partial pbp + Wk19),
  not a private note. Mirror the verified-context pattern of `_BUDGET_EVENT_CONTEXT`
  (`league_changes.py:440–446`).
- merge into `league_timeline()` at the same point `setting_change_events()` is folded in
  (`analytics/league_history.py:~575–577`). The web renders it automatically via `ChangeRow`
  (`web/src/features/league/LeagueHistoryPage.tsx:293–386`).

### 4 — Web (`web/src/features/`)
- `matchups/*` box-score component: render the resolution banner + the per-player "Wk17+19" badge
  with its stat breakdown (ideally showing the partial vs Wild-Card split).
- `records/RecordsPage.tsx` `ChampionshipTimeline` (157–208) and the bracket auto-correct; optional
  asterisk/footnote linking to the timeline event.

### 5 — Fixture DB + tests
- Regenerate the dashboard fixture DB from the corrected live ORM (the fixture is ORM-built, so it
  won't reflect the upstream fix until regenerated — see project memory "green gate ≠ real DB").
- Update known-answer assertions: 2022 champion = Smokin Doubs; title-game corrected totals.
- New tests: box-score substitution labelling + suppressed false-zero flag; curated timeline event
  present for 2022; `championships()` returns Smokin Doubs.

## Done when

- 2022 title-game box score shows **Doubs > CMC** (≈139 vs ≈101 with partials), a resolution banner,
  and the 4 substituted starters badged with their Wk17-partial + Wk19 breakdowns (no DNP/"unexpected"
  flags).
- Records championship timeline + seasons list show **2022 Smokin Doubs**.
- League History 2022 carries the curated Hamlin event with verified context + sources.
- Green gate passes (`green-gate` skill): backend pytest/ruff/mypy; frontend gen:api drift +
  typecheck/lint/test; e2e for matchup/records/league-history; manual click-through done.

Deliver as `feature/2022-championship-hamlin-context` → `dev`. Commit trailers
`AI-Model` / `Prompted-By` / `Reviewed-By`; never `Co-Authored-By: Claude`.
