# Plan — Insights Lab v0 (the non-viz "discovery engine" seed)

A first, concrete example of the **non-visualization** direction floated in
`phase3-nl-insights-exploration` and the Resonance charter's "discovery engine"
(`docs/PHASE2_5_RESONANCE.md` §North-star). Where the **Viz Lab** (`/lab`,
`web/src/features/lab/VizLabPage.tsx`) is a holding space for visual exhibits proving out
against real data, the **Insights Lab** (`/lab/insights`) is the parallel holding space for
**insight primitives** — text findings, no charts.

This is deliberately a **lab example**, not a shipped feature: one thin vertical slice that
establishes the *contract* and the *trust seam*, so the next insight is "just another primitive."

## The idea (and why it's the right non-viz seed)

An **insight primitive** is a named, tested `analytics/` function that **computes a structured
finding** from metrics we already have. A separate **narrator** renders prose from the finding's
facts. The trust seam is the project's own move, reused: just as the SPA is trustworthy because it
does no math, the narrator (a **deterministic template today, an LLM later**) only *arranges*
numbers it is handed — it **never computes one**. Every fact carries provenance to a tested metric
+ its serving endpoint. This is the Phase-3 "insight-primitive library" v0 (the analog of the
design system), built so an LLM narration/selection layer drops in later with the facts unchanged.

Honesty rule holds: a primitive returns `None` when a data gap means the finding can't be made —
an **absent** insight, never a fabricated one.

## The contract

`analytics/insights.py`:

```python
Insight = {
  "kind":       str,                 # "schedule_luck" | "draft_market"
  "title":      str,                 # short headline
  "narration":  str,                 # template prose built ONLY from facts (LLM-replaceable)
  "facts":      list[{"label": str, "value": str | float, "unit": str | None}],
  "subject":    {"owner_id": int | None, "owner_name": str | None} | None,
  "provenance": {"metric": str, "endpoint": str},
  "confidence": "high" | "medium" | "low",   # reflects DATA QUALITY, not effect size
}
```

`season_insights(session, season_id, cache=None) -> dict` collects the primitives, drops the ones
that returned `None`, and returns
`{season_id, season_year, available, insights: [...], notes: [str]}`.

### v0 primitives (reuse existing math — no new metric, only selection + narration)

1. **`schedule_luck`** — reuses `analytics/standings.standings_insights` (the xW/all-play
   keystone). Voices `most_robbed`: *"In {year}, {owner} was the league's unluckiest manager —
   {actual_wins} actual wins against an all-play résumé worth {expected_wins} (a {|luck_delta|}-win
   gap, the league's largest)."* Facts: actual_wins, expected_wins, luck_delta, all_play_win_pct.
   **Confidence:** `high` if the regular season is complete (`through_week ≥ 13`), else `medium`.
   Provenance: `standings.schedule_luck` → `/v1/seasons/{id}/standings/insights`.

2. **`draft_market`** — reuses `analytics/draft.draft_value` (`reaches[0]`, the recalibrated
   market axis). Voices the biggest reach: *"The draft's biggest reach: {player} at #{overall},
   {|adp_delta|} picks ahead of consensus ADP ({adp})."* Facts: overall, adp, adp_delta.
   **Confidence:** `medium` when `adp_coverage.limited` (no FFC draft-week snapshot), else `high`
   — directly reuses the coverage honesty shipped in PR #119. When limited, its note is appended
   to the season `notes`. Returns `None` when the season has no captured draft.

Two primitives are enough to prove: (a) the structured-finding contract, (b) facts/narration
separation, (c) reuse of two different existing metrics, (d) gap-driven absence, (e) data-quality
confidence.

## Files

- `src/ff_dashboard/analytics/insights.py` — primitives + `season_insights` + the `_narrate_*`
  template helpers. **All math/selection here; the narrator only formats handed-in facts.**
- `src/ff_dashboard/api/schemas.py` — `InsightFact`, `InsightProvenance`, `InsightSubject`,
  `Insight`, `LabInsights`.
- `src/ff_dashboard/api/routes/lab.py` — `GET /v1/lab/insights/{season_id}` →
  `Envelope[LabInsights]`; register in `api/main.py`. Lab-namespaced (clearly experimental).
- `web/src/features/lab/InsightsLabPage.tsx` — presentation-only insight cards (title, narration,
  fact chips, provenance line, confidence tag). Season from context, like other pages.
- `web/src/app/App.tsx` — `<Route path="lab/insights" .../>`.
- `web/src/app/shell/AppShell.tsx` — nav entry under the existing **Lab** divider.
- Tests: `tests/test_insights_lab.py` (primitives + builder + endpoint over the fixture DB);
  `web/src/features/lab/InsightsLabPage.test.tsx` (cards render from a mocked response), mirroring
  `VizLabPage.test.tsx`.

## Test list

- `schedule_luck` fires for 2016: narration names the most-robbed owner and contains the
  actual/expected numbers; facts present; subject set; confidence `high` (completed season).
- `draft_market` fires for 2016: biggest reach is Kelce (#1); facts carry adp/adp_delta;
  confidence `high` (2016 has FFC). A no-draft season → primitive returns `None`, omitted.
- `season_insights` drops `None` primitives; `available` false only when *no* primitive fired.
- Gap honesty: a limited-ADP season surfaces the coverage note in `notes` and `draft_market`
  confidence drops to `medium` (assert via a constructed/eligible season if the fixture has one;
  otherwise assert the wiring at the primitive level).
- Endpoint: `/v1/lab/insights/{2016}` returns the envelope with ≥1 insight; `gen:api` drift clean.
- FE: cards render title + narration + fact chips for a mocked `LabInsights`.

## Done when

- `analytics/insights.py` computes structured findings; the narrator only formats facts; gaps
  yield absent insights.
- `/v1/lab/insights/{season_id}` serves them; client regenerated.
- `/lab/insights` renders text insight cards under the Lab nav, presentation-only.
- Full gate green; click-through of `/lab/insights` for a real season (e.g. 2024) shows the
  schedule-luck + draft-market insights, and a limited-ADP season shows the coverage note.

## Explicitly out of scope (v0)

No LLM call (narration is a deterministic template — the seam is what matters); no NL question
input; no insight ranking/selection model; no new metric math. Those are the next lab iterations
once the contract has proven out.
