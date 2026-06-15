# Plan — Spreading the Rivalries strength across the dashboard

**Type:** post-roadmap product strategy + first two builds (not a P# milestone).
**Branch:** `feature/engagement-rivalries-strength` (cut from `dev`; PRs to `dev`).
**Companion read:** `docs/plans/rivalries-insights.md` — this plan generalises the lens that
page proved.

---

## 1. The thesis (why this work exists)

`/rivalries` is the most-loved page in the app, and not by accident. Reading
`web/src/features/rivalries/RivalryInsights.tsx`, its appeal decomposes into five moves:

1. **"Find your own row."** The Nemesis & Favorite Victim band is explicitly *"every active
   manager"* — a table you scan for *yourself* first. Stats about strangers are trivia; stats
   about *you and the people you beat* are personal.
2. **Opinionated superlatives, in voice.** "Biggest beating," "favorite victim," "currently
   riding" — human, faintly trash-talky language, not "max margin of victory."
3. **A transparent composite.** The heat index *ranks* rivalries and starts an argument, but
   shows its recipe — *"never a black box."* Rankings entertain because people disagree.
4. **Insight → receipts, one tap away.** Every line deep-links to its matchup / pairwise page.
   The claim is never the end; the evidence is always reachable.
5. **Honest gaps.** `DataGap`, never a fake 0–0. The discipline is what lets the playful
   framing land credibly.

**The goal, stated broadly:** *every page should give a league member a reason to look for
themselves, an opinion to react to, and a receipt to verify it — in the league's own voice.*
Most pages today nail the engineering (#4, #5) but are thin on the entertainment (#1–#3).
They are correct dashboards; Rivalries is a story.

## 2. The governing discipline — apply the lens *where it already fits*, never by force

The failure mode is **noise**: if narrative bands are bolted onto every page, Standings stops
being where you *read the table*, Stats stops being where you *look something up*, and the
reader loses the map of what each page is for. So the lens is applied by **tier**, and a page
only earns a higher tier if its *job* already invites it.

| Tier | What it is | Noise risk | Where |
|------|------------|-----------|-------|
| **0 — Voice** | Relabel cards / empty states / captions in the league's voice ("Biggest beating", not "Max margin"). Zero new pixels. | None | Everywhere, opportunistically |
| **1 — Personalization** | Highlight *your* row in an existing table. Changes emphasis, not structure. | Low | Any leaderboard |
| **2 — One signature insight** | Promote a stat the page *already computes* into a voiced headline. At most one per page. | Medium | Only where data already exists |
| **3 — Rich multi-band narrative** | The full Rivalries treatment. | High if scattered | **Concentrated** on lore pages only |

**The clarity test for any addition:** *if it makes you unsure whether you're on the stats page
or the stories page, it failed.* The engagement layer must make each page **more itself**, not
more like its neighbours.

### Canonical page-identity map (the noise guardrail — honour this in every future session)

| Page | Its job | Sanctioned move |
|------|---------|-----------------|
| Home | Front door / hub | Tier 3: "this week in league history" |
| **Manager profile** | *This person's* story | **Tier 3: lead with superlatives, in voice** |
| Records | Trophy case & extremes | Tier 3: Hall of Fame **& Shame**, all-time tiers |
| Stories | Long-form lore | Tier 3: auto season recaps |
| **Standings** | The table, honestly | **Tier 2: Schedule Luck → "Robbed / Blessed"** |
| Draft | Pick value | Tier 0: extend the existing Steals/Busts voice |
| Power / Stats / Players | Analysis & lookup | Tier 0–1 only. **No bands.** |
| Rivalries | Lore & entertainment | Already Tier 3 (done) |

Decisions already locked with the product owner:
- **No new "lore" page.** Tier-3 lore concentrates into the existing Home / Records / Stories.
- **The "you" lens (global manager pick) is a *nice-to-have*, built last and only if it stays a
  light, additive layer** (it mirrors `SeasonContext`, so the architecture is cheap; the only
  cost is per-table opt-in — start with 2–3 tables, stop the moment it feels like chrome).
- **Voice target:** entertainment + conversation-starters. The test for any line is *"would
  this start an argument in the group chat?"* — but it must never feel mean about real people.

---

## 3. This branch builds two things (the proof + the prize)

Ordered organic-fit × value ÷ effort. **#A first** (de-risk the voice on an analytical page
where clutter would hurt most), then **#B** (where a league member actually feels *seen*).
Everything in §5 is documented backlog, **not** built on this branch.

### A — Standings: "Robbed / Blessed" (Tier 2, the contained proof)

`analytics/standings.py` already computes per-team `luck_delta` / `expected_wins` /
`all_play_win_pct` (`all_play_index` + the schedule-luck insight reducer, ~L175–280). The card
exists on `StandingsPage.tsx` titled "Schedule Luck" with eyebrow "all-play vs actual wins".

**The move (no new math required):**
- Reframe the existing card with voice: title **"Robbed & Blessed"**, eyebrow stays honest
  ("all-play expected wins vs actual"). Lead with the single most-robbed and most-blessed team
  of the selected season as two callout lines ("**Robbed:** {team} won {actual}, *should* have
  won {expected} — the schedule cost them {|delta|}"), then the existing full ranked list below.
- Keep the explanation caption (it's the "never a black box" move). Keep the per-season scope —
  do **not** turn Standings into an all-time page; the all-time version belongs in Records (§5).
- Every row deep-links to that team's manager profile (consistency with the rest of the app).

**Files:** `web/src/features/standings/StandingsPage.tsx` (presentation only — the data is
already on the wire; confirm with `npm run gen:api` that no schema change is needed). If the
"most robbed/blessed" pick needs to be server-side for honesty/gating, add a tiny reducer to
`analytics/standings.py` and surface it on the existing standings response rather than computing
a max in `web/` (no metric math in the frontend — hard rule).

**Done when:** the card reads as a voiced headline + receipts; gaps still show `DataGap` for
unscored/in-progress seasons (never a 0); pre-2016 seasons behave (data-driven `is_scored`).

### B — Manager profile: "Your Story" (Tier 3, the prize)

The profile is fed by the `owners` route (`career`, `seasons`, `trajectory`, `rivalry-matrix`,
`head-to-head`). Today it's an honest *résumé* (trophy case, consistency, trajectory, season
table, rivalry snapshot). Its **job is to tell one person's story**, so it can carry the full
treatment without violating the noise guard — this is the one page where Tier 3 is native.

**The new lead band — "Your Story" (a personal highlight reel), above the existing cards:**
A small set of per-owner superlatives, each one a voiced line that deep-links to its receipt.
All of it reduces from data the app already loads — primarily `head_to_head.all_pairwise()`
(the exact source the rivalries bundle uses) filtered to this owner, plus per-season schedule
luck and the existing championship/records data. Candidate lines (gate each; show only those
that clear a min-sample bar — **never force a label or fabricate a 0**):

- **Signature win** — biggest beating they ever handed out (margin), linked to the box score.
- **Heartbreak** — closest loss, ideally a playoff elimination if one exists.
- **Kryptonite (nemesis)** — worst all-time record vs one manager (reuse the rivalries nemesis
  reducer, scoped to this owner; min-sample gated).
- **Favourite victim** — best all-time record vs one manager.
- **Luckiest / unluckiest season** — max / min `luck_delta` season for this owner (reuse §A's
  per-season luck; "in {year} the schedule *gave* / *robbed* them {n} wins").
- **High-water mark** — single highest score they ever posted, linked to the box score.

**The stretch — a per-manager epithet (the potential "groundbreaking" piece).**
A one-line *archetype* derived from the owner's statistical fingerprint — e.g. *"The
Heartbreaker — more single-digit losses than anyone, and the best all-play record never to win
a title."* This is the highest-ceiling, highest-taste-risk element: done well it's the most
screenshot-able, conversation-starting content in the app; done carelessly it's noise or feels
unfair. **Guardrails, non-negotiable:**
- Each epithet is assigned *only* when the data strongly and unambiguously supports it (a
  documented threshold per archetype, in `analytics/`, tested on the fixture DB). If no
  archetype clears its bar, the owner simply gets **no epithet** — never a forced or generic one.
- A small, fixed, affectionate vocabulary of archetypes (e.g. The Heartbreaker, The Closer, The
  Lucky Devil, The Sleeping Giant, The Bridesmaid) — celebratory or wry, never cruel about a
  real person.
- It is **gated behind the product owner's eye in the VERIFY session** — ship the superlatives
  first; treat the epithet as a reviewable proposal, not an auto-merge.

**Files:**
- `src/ff_dashboard/analytics/owners.py` (or a new `analytics/owner_story.py` if it grows) —
  new pure reducer `owner_story(session, owner_id) -> {...}` over `all_pairwise()` + per-season
  luck + records. All math here, tested against the fixture DB's known answers.
- `src/ff_dashboard/api/routes/owners.py` — new endpoint `GET /v1/owners/{owner_id}/story`
  returning the bundle (each superlative carries `available` / `reason` per the envelope norm).
- `src/ff_dashboard/api/schemas.py` — schema for the bundle.
- `web/src/features/managers/ManagerProfilePage.tsx` + a new `ManagerStory.tsx` component
  (mirrors `RivalryInsights.tsx`'s band structure). Run `npm run gen:api`; never hand-edit the
  client.

**Done when:** the profile leads with the story band; every line deep-links; gated lines that
don't clear their bar are simply absent (not 0, not "—" with a fake value); the epithet (if
included) has reviewed thresholds and the owner has signed off on the vocabulary.

---

## 4. Test list

**Backend (`tests/dashboard/`):**
- `test_standings.py` — extend: most-robbed / most-blessed selection matches the known fixture
  season; ties broken deterministically; unscored season → unavailable, not a 0.
- `test_owners.py` (or new `test_owner_story.py`) — `owner_story()` known-answer cases on the
  fixture DB: signature win / heartbreak / nemesis / favourite victim / luck extremes; min-sample
  gates drop thin pairings; an owner with sparse history yields a mostly-empty-but-valid bundle.
- Epithet thresholds (if built): each archetype's rule fires on a constructed fixture case and
  *does not* fire just below its bar.

**Frontend:**
- `StandingsPage.test.tsx` — Robbed/Blessed callouts render; `DataGap` on unscored season.
- `ManagerProfilePage.test.tsx` — story band renders; absent superlatives don't render empty
  rows; links point at the right matchup/manager routes.
- `npm run gen:api && git diff --exit-code web/src/lib/api` — contract drift check after the new
  endpoint.

**Gate:** the full green gate (`.claude/skills/green-gate`) once, at the end of each BUILD; e2e
only in VERIFY.

---

## 5. Documented backlog (NOT built on this branch — captured so the strategy survives)

These are the rest of the lanes, parked with their sanctioned tier so a future session can pick
one up without re-deriving the discipline:

- **Home — "This week in league history"** (Tier 3): the same calendar-week's classic matchups
  from past seasons; a recurring reason to return. Reduces from existing matchup records.
- **Records — Hall of Fame & Shame + all-time manager tiers** (Tier 3): the all-time schedule-
  luck superlative ("flukiest title"), biggest chokes (best regular season → earliest exit), and
  an opinionated all-time manager tier list (the single most argument-generating artifact).
- **Stories — auto season recaps** (Tier 3): "the {year} season in 5 beats", assembled from
  records already computed.
- **Draft** (Tier 0): extend the Steals/Busts voice; "best/worst pick of all time", draft-day
  nemeses.
- **Connective tissue** (Tier 1, *strictest* noise rule): inline one-liners only where obviously
  relevant — e.g. a box score between two top-5-rivalry managers gets one line; a random regular-
  season game gets nothing.
- **The "you" lens** (Tier 1, conditional): a `MeContext` mirroring `SeasonContext` + a shell
  control + per-table row highlight, rolled out to 2–3 tables first. Build only if it stays light.

---

## 6. Handoff prompts for fresh sessions

Copy-paste one of these into a new thread. Each is self-contained; the session should read this
plan first, then only the doc sections it cites.

### → BUILD session A (Standings "Robbed / Blessed")

```
Continue feature/engagement-rivalries-strength. Read docs/plans/engagement-rivalries-strength.md
§2–§3A and §4, and PROGRESS.md. Build item A only: reframe the Standings "Schedule Luck" card as
"Robbed & Blessed" — voiced most-robbed/most-blessed callouts above the existing ranked list,
rows deep-link to manager profiles, gaps stay DataGap (never 0), per-season scope unchanged.
Data is already on the wire; if the most-robbed/blessed pick must be server-side for honesty,
add a small reducer to analytics/standings.py rather than computing a max in web/ (no frontend
math — hard rule). Add the tests in §4. Run the green gate once at the end. Honour the noise
guardrail in §2: this is Tier 2 — do NOT add bands or turn Standings into an all-time page.
Update PROGRESS.md and commit with the AI-Model / Prompted-By / Reviewed-By trailers (never
Co-Authored-By: Claude). Do not open a PR until asked.
```

### → BUILD session B (Manager profile "Your Story")

```
Continue feature/engagement-rivalries-strength. Read docs/plans/engagement-rivalries-strength.md
§1–§2 and §3B and §4, plus docs/04_ANALYTICS_MODEL.md for the head_to_head/rivalries reducers and
docs/05_API_CONTRACT.md for the owners endpoints. Build item B: add a pure owner_story() reducer
(analytics/) over head_to_head.all_pairwise() + per-season schedule luck + records, a
GET /v1/owners/{id}/story endpoint, and a "Your Story" lead band on ManagerProfilePage (new
ManagerStory.tsx, mirroring RivalryInsights.tsx). Every superlative gates on a min-sample bar and
is simply ABSENT when it doesn't clear it — never a forced 0 or fake value. Build the superlatives
first; treat the per-manager epithet (§3B stretch) as a SEPARATE, reviewable proposal with
documented, tested thresholds — do not auto-ship it. Run gen:api (never hand-edit the client) and
the drift check; add the §4 tests; run the green gate once at the end. Update PROGRESS.md and
commit with the standard trailers. Do not open a PR until asked.
```

### → VERIFY session (either item)

```
Continue feature/engagement-rivalries-strength. Use the green-gate and verify skills. Run the
full gate (backend pytest+ruff+mypy; frontend gen:api drift + typecheck+lint+test; e2e), fix only
real failures, then click through /standings and /managers/{id} in the running app. For the
Manager-profile epithet specifically: present the assigned archetypes + their thresholds to the
product owner as a proposal and get sign-off on the vocabulary/voice BEFORE keeping it. Confirm the
§3 "Done when" for the built item. Commit with the standard trailers.
```

---

## 7. Done when (this plan's own definition)

- The SOON-tag fix on `/rivalries` (`AppShell.tsx ready:true`) lands on this branch. ✅ (in tree)
- Items A and B are built per §3, green per §4, clicked through per §6 VERIFY.
- The strategy in §1–§2 + the §5 backlog are committed so future sessions inherit the lens and
  the noise guardrail without re-deriving them.
- `PROGRESS.md` updated; commits carry the trailer format; PRs target `dev`.
