# Handoff — danger-zone: faithful DST points-allowed re-derivation

> **Audience:** an agent working in `../danger-zone` (Phase 1 / ff-pipeline). This is an
> **upstream** job — it changes `player_stats_scored.total_points`. The dz-dashboard SPA is
> read-only and needs **zero changes**; it already shows the authoritative number via the
> `analytics/scoring.py` coalesce. **Authored from** a dz-dashboard investigation, 2026-06-24.
> **Companions:** `docs/plans/dst-deep-classification.md` (deep census — but see the correction
> below), memory `dst-yards-sacks-pipeline-gap`, `reconstruction-fidelity-direction`.
>
> **Important:** this handoff supersedes the PA section of `docs/plans/dst-deep-classification.md`.
> Treat that older section as historical evidence only; do **not** copy its "PA = final score"
> implementation plan.
>
> **Outcome update (2026-06-24):** the upstream attempt in `../danger-zone` found no safe
> material PA shrink. A pure structured-`play_type` classifier resolved ARI 2016 wk3 but
> regressed SEA 2013 wk6; copy validation over 2010–2025: `RESOLVED=0`, `IMPROVED=0`,
> `UNCHANGED=127`, `WORSENED=0`, `REGRESSED=0`. Live DB deliberately **not** rewritten.
>
> **Deep audit (2026-06-24, dz-dashboard side) — the PA class is now PROVEN irreducible, and the
> `play_type` framing was a red herring.** The 79 PA rows are **not** special-teams cases: every one
> is a game where `_score_counts_against_dst` excluded an opponent **scrimmage defensive return TD**
> (pick-six / fumble-six, `play_type='pass'/'run'`, `td_team!=posteam`), leaving our PA exactly
> **7/8/9 below the opponent's final score** (75×−7, 7×−9, 3×−8); smeared evenly across all 16
> seasons. That is why the `play_type` change resolved 0 rows — it can only touch kick/punt/FG returns,
> which are not the issue here. Two whole-set offline tests settle it: **(1)** among DEF-weeks where an
> exclusion moves the PA bracket, the exclusion is **correct in 287 rows** and **wrong in only 94**
> (the 79 PA + ~15 bracket-edge OTHERs) — so sourcing PA from the opponent's full final score would
> **break 287 currently-correct rows**, permanently refuting "PA = final score" and reproducing the GB
> 2020 wk6 canary at scale; **(2)** the 94 wrong-exclusions and the 287 correct-exclusions carry the
> **same INT:FUM mix** (DIVERGE 47 INT / 33 FUM vs MATCH 158 INT / 83 FUM) — identical play types in
> both buckets, **no nflverse-PBP feature separates them**. **(3)** Explicitly tested the "year-to-year
> scoring-rule change" hypothesis: every season is an **11–44% charged/excluded mix** — no season near
> 0/100%, no transition year — so it is not a per-season rule. **The decisive canary is HOU 2013 wk2 vs
> wk5:** the same defense, same season, a **Matt Schaub pick-six in both games**; NFL.com *excluded* it
> from points-allowed in wk2 (PA 17 → matches) but *included* it in wk5 (PA 34 → diverges). A scoring
> rule cannot change between week 2 and week 5 of one season — the inconsistency is at the
> individual-game level, in NFL.com's own box-score feed. **Conclusion: genuine source noise, not a
> classifier bug and not a rule change. Do not change `_index_fantasy_points_allowed`; do not override
> rows. The workstream is closed.**

---

## TL;DR

There is **one substantial workstream left** in the scoring-reconstruction fidelity effort, and
**one that is already closed** (don't re-open it):

| | Rows | Status |
|---|---|---|
| **A. DST `points_allowed` re-derivation** | ~79 | **DO THIS.** Faithful PBP re-derivation, mirroring the TD recount. |
| **B. Offensive bonus/score residual** | 69 / 35,946 (0.19%) | **CLOSED — no action.** Pure source disagreement; §B documents why, so it isn't re-litigated. |

Ground truth is `team_rosters.extra_data.nfl_com_points` (the scraped NFL.com league score, present
on rostered player-weeks). Current state: total diverging rostered DST rows **127** (was 500 → 303
after the relocation join, → 127 after the TD recount). Of the 127: **~79 points-allowed** + **~48
small sacks/yards one-offs**. The offensive side is at 69 scattered rows.

**Done bar (set by the owner):** a comprehensive, *best-attempt* re-derivation. **Approaching zero is
the aspiration, not the gate.** A documented residual is acceptable. The hard requirement is **zero
regressions** (no currently-correct row newly broken) — the same discipline as the TD recount.

**Method (owner's choice):** reverse-engineer the correct behavior empirically against the
`nfl_com_points` oracle. Promote a classification change only when it holds across many rows/seasons;
quarantine and **escalate genuinely ambiguous rows to the owner — only if absolutely necessary.**

---

## Background: how DST scoring works here, and where PA fits

`build_team_defense_stats` (`src/ff_pipeline/crawlers/nflverse/team_defense.py`) assembles each
defense's weekly stat line, which the engine (`scoring/engine.py`) scores against the league's
per-season `scoring_rules`. `points_allowed` is scored by a **bracket** rule (flat points for a range,
e.g. 0 → big bonus, 1–6 → less, 7–13 → less, …). So **a PA that is off by even 1 point can flip the
bracket** and shift the score by the bracket step (the gaps we see are ±1/±3).

PA is **derived from play-by-play**, not taken from the final score, by
`_index_fantasy_points_allowed(pbp_rows)`:

- It walks each game's PBP rows in order, detecting each scoring event by the cumulative
  `total_home_score` / `total_away_score` delta.
- For each scoring event it asks `_score_counts_against_dst(...)`: *do these points count against the
  conceding team's D/ST?*
- It **excludes** points the opponent scored *against the team's offense* (a pick-six / fumble-six the
  opponent's defense returned) and **safeties**, because the D/ST wasn't on the field for those. It
  **includes** kick/punt return TDs (the special-teams half of the D/ST allowed them). Extra points /
  2-pt tries inherit the preceding TD's classification.

`_score_counts_against_dst` is the classifier. Its special-teams-return test,
`_is_special_teams_return_touchdown`, currently works by **string-matching the play `desc`** (looking
for `" punt"`, `"kicks"`, `"kickoff"`, `"field goal"`).

---

## Workstream A — the corrected thesis (READ THIS; the old plan is partly wrong)

`docs/plans/dst-deep-classification.md` "Class A" proposed: *the exclusion is an unverified theory;
NFL.com's D/ST points-allowed is simply the opponent's final score, so delete the exclusion and source
PA from the final score.* **That hypothesis was refuted later in the same investigation and must NOT be
followed:**

- **Counter-example (decisive):** **GB 2020 wk6** — our derived `PA = 31`, the opponent's final score
  was `38`, and `nfl_com_points` reconciles with **31, not 38**. The 7-point difference is a
  **pick-six GB's offense threw** — correctly excluded. So the exclusion logic is **right** here, and
  "PA = final score" would *break* this currently-correct row.

So the two findings reconcile into the actual rule NFL.com appears to use:

> **D/ST points allowed = every point the opponent scored, EXCEPT points scored directly against this
> team's offense (defensive return TDs + their XP/2pt, and safeties). Special-teams return TDs DO
> count (the ST half allowed them).**

That is essentially what `_score_counts_against_dst` already encodes. **The remaining ~79 errors are
therefore edge-case misclassifications, not a wrong theory** — the classifier is mostly right (GB
proves the core), but mislabels specific scoring events at the margin, which nudges PA across a bracket
boundary.

### The most likely root cause (tested; only partly useful)

`_is_special_teams_return_touchdown` uses **brittle `desc` string-matching**, whereas the **proven TD
recount** (`_index_dst_touchdowns`, landed 2026-06-23) classifies special-teams scores by the
**structured `play_type` column** (`kickoff` / `punt` / `field_goal`). The two code paths disagree on
what's a special-teams return — and that inconsistency is the prime suspect for the PA bracket flips
(a defensive return TD mislabeled ST, or vice-versa, charges/relieves PA by ~6–8 and flips the
bracket).

**Result:** making `_score_counts_against_dst` classify special-teams returns by `play_type`
(reusing `_SPECIAL_TEAMS_TD_PLAY_TYPES`) is safe for kickoff/punt/FG return tests, but it does **not**
shrink the live residual once the SEA 2013 wk6 field-goal-formation canary is preserved. nflverse has
no clean structured field for that formation; the narrow description fallback remains necessary.

### Step-by-step

1. **Re-run the offline audit** (no network) to refresh the census on the current live DB:
   `cd ../danger-zone && uv run python scripts/audit_dst_divergence.py` — confirm ~79 `PA` +
   the OTHER classes. Use `--detail PA` to dump the rows (season, week, team, our PA, opp final).
   Save this as the "before" artifact in the PR notes.
2. **Classify the 79 by cause.** For each, pull the game's PBP and find the scoring event(s) whose
   inclusion/exclusion would move our PA into the bracket that matches `nfl_com_points`. Expect a
   dominant pattern (mislabeled ST vs defensive return TD). Confirm the `play_type` vs `desc`
   disagreement is the driver on a sample. Minimum useful sample: several seasons, at least one
   kickoff/punt return, at least one blocked kick / field-goal return, and the GB 2020 wk6
   counter-example as a must-not-regress canary.
3. **Implement** the `play_type`-based classification in `_score_counts_against_dst`, with the narrow
   field-goal-formation fallback documented above. Unit-test offline first:
   `tests/unit/test_team_defense.py` has a `_pbp_score` / `_pbp` helper for hand-built PBP rows — add
   cases for: a defensive return TD (excluded), a kickoff/punt return TD (included), a safety
   (excluded), a blocked-FG return, aborted field-goal formation, and XP/2pt inheritance after each.
4. **Validate on a DB copy** (see Mechanics) with the **zero-regression gate**. This was done
   2026-06-24 and produced `RESOLVED=0`, `WORSENED=0`, `REGRESSED=0`.
5. **Document the residual.** Any PA rows that remain after a faithful classifier are likely genuine
   source disagreements (nflverse PBP vs NFL.com's box score). Record them; do not override row-by-row
   to force a match (that destroys the reconstruction's value as an independent check — see
   `reconstruction-fidelity-direction`). **Escalate to the owner only if a row is genuinely ambiguous
   and material.**

### Guardrails

- **Only ever change behavior that is validated across multiple rows/seasons.** A one-row override is
  not a fix; it's quarantine-and-document territory.
- **Do not replace PA with opponent final score.** That breaks currently-correct rows where the
  opponent scored against this team's offense. GB 2020 wk6 is the explicit canary.
- **Do not change raw PBP/team-stat facts to make a score match.** The valid change is the derived
  classifier or a faithful downstream stat derivation. Raw source rows remain raw.
- **The `~48 OTHER` (sacks/yards ±1/±2/±3) are out of scope here** unless a PA fix happens to touch
  them. They are residual one-offs, not a systematic class. Note any that the PA work incidentally
  resolves.

### Implementation notes for the classifier

The safe target shape is to make PA classification use the same structured return-TD vocabulary as the
already-proven TD recount where nflverse exposes enough structure:

- Add `play_type` to the scoring-event context passed into `_score_counts_against_dst`.
- Replace the broad `desc` substring heuristic in `_is_special_teams_return_touchdown` with
  `play_type in _SPECIAL_TEAMS_TD_PLAY_TYPES`, plus only the narrow `"(Field Goal formation)"`
  fallback needed for SEA 2013 wk6.
- Keep the existing semantic split: opponent defensive return TDs and safeties are excluded from PA;
  opponent special-teams return TDs count against the D/ST; XP/2pt attempts inherit the preceding TD's
  include/exclude decision.
- If a remaining row needs a different rule, prove it with repeated examples before changing behavior.
  Single-row oddities belong in the residual table.

---

## Workstream B — offensive residual: CLOSED, do not reverse-engineer

A full empirical bonus reverse-engineering pass was **considered and ruled out** with evidence
(2026-06-24). Recorded here so it is not re-attempted:

- Offensive divergence is **69 of 35,946 rostered offensive player-weeks (0.19%)**. The league's
  scoring rules are **complete and correctly versioned per season** — they load from the NFL.com
  `/settings` CSV exports via `ff-pipeline scoring load`, so real historical changes (e.g. **2010:
  6-pt passing TD + 0.5-PPR → 2011+: 4-pt passing TD + full PPR**) are already captured. A captured
  change cannot cause drift; only an *uncaptured* one could, and none exists.
- The 69 are **stat-source disagreements, not missing rules**, proven three ways: (1) **no season
  clustering** (smeared 2010–2025; 2014/2016/2018/2021 are zero; worst in the *oldest* seasons = data
  aging); (2) **42 of 69 gaps are fractional** (0.12, 0.3, 1.32…) — mechanically impossible from an
  integer bonus rule, so they can only be per-yard accrual over a yardage the sources differ on; (3)
  every **integer** gap traces to an **existing** rule applied to a disputed input — e.g. **Chad Henne
  2010 wk7**: rule `passing_interceptions = −2` is present and correct, nflverse's weekly line says
  0 INTs, NFL.com docked −2 (says 1 INT) → the *sources disagree on the fact*, not the formula. Every
  `+2` row has `fumbles_lost ≥ 1` (a lost fumble NFL.com didn't charge); `−2`/`−1` are INT/fumble/
  reception-count disagreements.
- **The only PBP-re-derivable sliver** (a handful of fumbles/INTs nflverse's weekly rollup missed) is
  the same species as the DST fix but **low-yield** — the `backfill_fumbles_lost.py` sweep already
  took the bulk (offensive negatives 124→36). **Not worth a workstream.** If Workstream A's PBP
  tooling is in hand and cheap to extend, a *fumbles/INT-from-PBP* spot-check is optional, not
  expected.

If the owner later wants the offensive residual driven lower anyway, it is **stat re-derivation from
PBP, not rule reverse-engineering** — frame it that way.

---

## Mechanics, commands, and the validation gate

**Cross-repo:** code + DB live in `../danger-zone`. Live DB: `../danger-zone/data/fantasy.db`
(read-only from the dashboard; the pipeline owns writes).

**Network requirement (the one real blocker):** PBP is **not cached** (`data/nflverse_cache/` is
empty; cache mode is in-memory). The crawler logic + unit tests + the offline audit run **without
network**; only the live re-ingest needs github reachability to re-load PBP.

**Re-ingest is per-season and robust** (each season is an independent network call — loop so a hiccup
isolates to one season):

```bash
cd ../danger-zone
for yr in $(seq 2010 2025); do
  DATABASE_URL="sqlite:///./data/fantasy_validation.db" \
    uv run ff-pipeline team-defense --season $yr || echo "FAIL $yr"
done
DATABASE_URL="sqlite:///./data/fantasy_validation.db" uv run ff-pipeline rescore
```

**The zero-regression validation gate (proven on the TD recount — reproduce it exactly):**

1. `cp data/fantasy.db data/fantasy_validation.db` (back up; the copy is ~570 MB).
2. **Snapshot before:** for every rostered DEF week, record `(season,week,player_id) -> (nfl_com_points,
   total_points)` from the copy. (A ~30-line script: join `team_rosters` → `players` (position='DEF')
   → `seasons` → `player_stats_scored`, reading `json_extract(extra_data,'$.nfl_com_points')`.)
3. Re-ingest team-defense (the loop above, against the **copy**) + `rescore`.
4. **Snapshot after**, then **diff**: classify each row RESOLVED / REGRESSED / IMPROVED / WORSENED.
   **Require `REGRESSED == 0` and `WORSENED == 0`.** Expect a chunk of the 79 RESOLVED.
5. Re-run `scripts/audit_dst_divergence.py --db sqlite:///./data/fantasy_validation.db` → confirm the
   PA class shrank and nothing else grew.
6. **Only then** apply to the live `data/fantasy.db` (same loop without the `DATABASE_URL` override +
   `rescore`), back up first, and re-audit to confirm the copy's numbers reproduce.

The diff artifact should include the counts and examples for:

- `RESOLVED`: was divergent, now matches `nfl_com_points`.
- `IMPROVED`: still divergent, but absolute delta shrank.
- `UNCHANGED`: still divergent by the same delta.
- `WORSENED`: was divergent and moved farther away. Must be zero.
- `REGRESSED`: previously matched and now diverges. Must be zero.

For residual PA rows, record `(season, week, team, player_id, our_pa_before, our_pa_after,
opponent_final, nfl_com_points, total_points_after, suspected event)` so the owner can review without
re-running the whole audit.

**Green gate before PR:** `uv run pytest tests/unit/test_team_defense.py -q`, then
`uv run ruff check -q && uv run ruff format --check && uv run mypy src/ff_pipeline`.

**Git model:** `feature/*` off `dev` → PR to `dev` (danger-zone). Commit trailers `AI-Model` /
`Prompted-By` / `Reviewed-By`; never `Co-Authored-By: Claude`. Delete the branch after merge.

---

## Key files & symbols

- `src/ff_pipeline/crawlers/nflverse/team_defense.py`
  - `_index_fantasy_points_allowed` — the PA derivation (scoring-delta walk).
  - `_score_counts_against_dst` — **the classifier to fix** (which scoring events count).
  - `_is_special_teams_return_touchdown` — the **brittle `desc`-based** ST test to replace with
    `play_type`.
  - `_index_dst_touchdowns` + `_SPECIAL_TEAMS_TD_PLAY_TYPES` — the **proven `play_type` pattern** to
    mirror.
  - `build_team_defense_stats` — assembles the stat line; PA flows in here, final-score is the
    fallback.
- `scripts/audit_dst_divergence.py` — offline census + `--detail PA` row dump (your primary diagnostic).
- `tests/unit/test_team_defense.py` — offline PBP unit-test harness (`_pbp` / `_pbp_score` helpers).
- `cli.py` commands: `team-defense --season YYYY`, `rescore` (both honor `DATABASE_URL`).
- `docs/plans/dst-deep-classification.md` — update only after the danger-zone result is known; mark the
  PA-final-score thesis as refuted and summarize the actual residual.

## Done when

- The PA classifier is re-derived faithfully from `play_type`; unit tests cover the return-TD /
  safety / XP-2pt cases.
- Validated on a copy with **0 regressions / 0 worsened**, a material chunk of the 79 PA rows resolved,
  applied to the live DB, re-audit confirms.
- Residual PA rows (if any) documented as genuine source disagreements; owner escalation only if
  truly necessary.
- `dst-yards-sacks-pipeline-gap` memory + `docs/plans/dst-deep-classification.md` updated with the
  outcome (and the "PA = final score" hypothesis marked refuted).
- No dashboard change. Green gate passed. Committed via `feature/*` → `dev` PR.
