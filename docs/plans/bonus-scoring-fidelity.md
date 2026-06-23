# Plan — Bonus-scoring fidelity (the `total_points` drift)

**Status:** plan / awaiting build go-ahead
**Trigger:** 2010 Stats → Top Scorers showed Mike Vick wk10 = **58.32**, but the matchup page,
his player page, and NFL.com all show **63.32**. Investigation found a league-wide, every-season
drift, not a 2010 quirk.

---

## 1. Root cause (confirmed against the live DB)

The danger-zone scoring **reconstruction** (`player_stats_scored.total_points`) computes only base
categories — `passing / rushing / receiving / kicking / misc`. **It carries no scoring bonuses.**
Verified: **0 of ~390k** scored rows have any `bonus` component in `points_breakdown`.

The authoritative, bonus-inclusive league score is `team_rosters.extra_data.nfl_com_points` — the
scraped NFL.com league result — but it exists **only for rostered player-weeks** (46,521 rows).

Scope of divergence (rostered rows where the two disagree by >0.05):

| seasons | rostered rows diverging / season | bonus points missing / season |
|---|---|---|
| 2010–2024 | ~140–220 | ~390–680 |

(2025 in progress.) Vick 2010: wk10 +5.00, wk3 +5.00, wk14 +4.00, wk15 +4.00, wk2 +1.00 — classic
NFL.com passing-yardage + long-TD bonuses.

**Why some surfaces are right and others drift:** the codebase already prefers `nfl_com_points` in
the *box score* (`matchups.py`), the *player weekly* (`player_scoring`), and the *records book*
(`records.py`, `coalesce(nfl_com_points, total_points)` over **started** rows). The drifting surfaces
read **raw `total_points`** instead.

**Upstream capability already exists:** `ff_pipeline/scoring/engine.py` fully supports flat threshold
bonuses (`flat_points`, `threshold_min/max`); `rules.py` defines the rule shape; there is a
`long_td_bonus.py`. The engine comment notes nflverse long-TD bonuses were **"deferred to M7."** So
the gap is **the per-season bonus rules were never fully seeded / applied** when the current
`player_stats_scored` was produced — *not* a missing engine feature. This is the open validation half
of **F-27** and the missing-backbone **per-season config ledger** (ACTIVE_WORK §2/§3).

---

## 2. Design decisions (owner: ocmooch, 2026-06-22)

1. **Upstream is the home for the fix**, on conditions: raw ingested stats stay **unadulterated**;
   per-season **scoring/bonus settings are a separate downstream layer** applied on top, **matched to
   the year** the performance occurred (settings changed over league history — already inventoried in
   `docs/archive/seasons-league-changes-inventory.md`).
2. **Records & team/owner attributions = started-only.** No league/team/owner record (highest weekly,
   season-high, monster-game) may be held by a **benched** or **unrostered** performance. A bench player
   who outscored the lineup is a **"missed opportunity"** — may be surfaced as a non-record curio in
   team/owner context, never as an attribution.
3. **The performance is still displayed, player-side.** The dashboard is a view of *this* league, so a
   player rostered **at any point in league history** has their full stat line shown — with year-matched
   bonuses applied — even for weeks/seasons they weren't rostered. The *player* gets the bookkeeping; the
   team/owner does not. (Hypothetical: "John Doe" 100 pts in a week no one rostered him = on his player
   page, with bonuses; never a league/team/owner record.)
4. **Seed never-rostered players out of the *view*, not the DB.** DB fact: `player_stats_scored` spans
   the **whole NFL** — **1,380 of 2,612** scored players were **never** rostered in league history. The
   pipeline **retains** all of them and their raw stats (lossless, no re-ingestion if one is later
   rostered); the **dashboard** simply doesn't render never-rostered players. Relevance is a view
   concern, enforced at the presentation layer.
5. **Apply the bonus layer uniformly to all players in the re-score** (not conditional on roster
   membership). Keeps scoring a pure, roster-agnostic `stats → points` function; the bonus compute is
   trivial arithmetic on already-ingested stats. Crucially this **avoids any re-score when a player
   later joins a roster** — their bonus-inclusive history is already correct. (Conditional bonuses would
   couple scoring to mutable roster state and force a back-fill re-score on every roster entry — the
   exact cost we want to avoid.) Never-rostered weeks lack `nfl_com_points` ground truth, so they're
   correct-by-construction from the validated rules, and hidden from view regardless — stakes nil.

---

## 3. Two-layer resolution

### 3a. Upstream (danger-zone) — the durable, single-source fix (extends F-27 + config ledger)
> Full upstream brief: **`docs/handoffs/bonus-scoring-rescore.md`** (delta distribution, validation gate,
> the negative-delta secondary finding).
- Seed the **per-season bonus rule set** into the scoring config (passing/rushing/receiving yardage
  bonuses, long-TD, any DST/K bonuses), **year-matched** to the league-settings ledger; finish the
  M7-deferred long-TD bonus wiring.
- **Re-score** 2010–2025 so `player_stats_scored.total_points` includes bonuses for **all** players
  (the only way to fix **unrostered** weeks — the BFF cannot, having no `nfl_com_points` to borrow).
- **Validation gate:** for rostered weeks, re-scored `total_points` must match `nfl_com_points` within
  0.1 (ground truth). Raw stats untouched; bonuses live in the settings layer.
- Outcome: every consumer becomes correct; the BFF coalesce below can later be dropped.

### 3b. Dashboard (BFF) — interim correctness now + the attribution rules (regardless of upstream timing)
Prefer `nfl_com_points`, fall back to `total_points` (matches records/matchups/player_scoring). Apply
the started-only / rostered-ever rules. Surfaces:

| Surface | File / source | Change |
|---|---|---|
| Stats → **Top Scorers** (reported) | Phase-1 `queries.top_scorers` | Reimplement in `analytics/stats.py` (like `season_totals` already is): coalesce `nfl_com_points`→`total_points`; **filter to rostered-ever**; player-credit (incl. non-rostered weeks of rostered-ever players), **not** a team/owner record. |
| **Home** "top scorers" card | `web/.../home/HomePage.tsx:69` → same `/v1/stats/top-scorers` (limit 5) | No FE change needed — fixing the endpoint fixes this card too. Just re-baseline its expectation. |
| Stats → **Season Totals** | `analytics/stats.py` `season_totals` | Per-week coalesce before summing; **filter to rostered-ever**. Do **not** strict-roster-scope (top season scorers had 47–93% roster coverage — dropping unrostered weeks would deflate totals). |
| Player → **Insights** best week/season | `analytics/players.py` `player_insights` | Coalesce authoritative score. Player-side, so non-started counts as *player* credit (still surfaced), but label honestly. |
| **Matchup monster-game flag** | `analytics/matchup_flags.py` `_top_starter_weeks` | Already started-only (`is_starter`); switch raw `total_points` → coalesce authoritative. |
| **Draft impact** | `analytics/draft.py` | Sums raw `total_points`; switch to coalesce authoritative for value consistency. |
| Records best_player_week | `analytics/records.py` | **Already compliant** (started-only + coalesce). No change. |

**Optional follow-up (new, not required):** "missed opportunity" — highest **benched** week per team/
owner, surfaced as a non-record curio.

---

## 4. Sequencing
1. **BFF interim** (3b): makes every displayed number correct for the rostered majority — all top
   season scorers, the #1 week in 14/16 seasons — and enforces the attribution rules immediately.
2. **Upstream** (3a): the true fix; also corrects unrostered weeks; later lets the BFF drop the coalesce.

## 5. Build anchors (so a cold-start session needn't re-discover)

**Live DB:** `../danger-zone/data/fantasy.db` (read-only). ⚠️ the repo-local `data/fantasy.db` is a
**0-byte stub** — don't query it. Env override: `DATABASE_URL` (see `.env.example`).

**Verification fixture (the canary):** Mike Vick `player_id=23907`, 2010 (`season_id=2`), **wk10**:
`player_stats_scored.total_points = 58.32`, `team_rosters.extra_data.nfl_com_points = 63.32` →
**target = 63.32**. His other 2010 gaps: wk3 +5.0, wk14 +4.0, wk15 +4.0, wk2 +1.0. Whole-DB scope:
~140–220 diverging rostered rows/season, 2010–2024.

**Idiom to copy (already correct in the tree):** `analytics/records.py:212-213` —
`coalesce(cast(json_extract(TeamRoster.extra_data,'$.nfl_com_points'), Float), PlayerStatsScored.total_points)`,
joined `TeamRoster ⨝ PlayerStatsScored` on `(player_id, season_id|season_year, week)`.
`analytics/stats.py:season_totals` is the template for a dashboard-owned, week-capped aggregate.
**Rostered-ever filter:** `EXISTS(SELECT 1 FROM team_rosters tr WHERE tr.player_id = … AND tr.week > 0)`.

**Route / contract:** `api/routes/players.py:114` (`/v1/stats/top-scorers`) and `:134`
(`/v1/stats/season-totals`); schemas `TopScorer/TopScorers/SeasonTotal/SeasonTotals` in
`api/schemas.py`. Top-scorers is currently imported from **Phase-1** `queries.top_scorers`
(`routes/players.py:11`) — move it to `analytics/stats.py:top_scorers`, swap the import, and **keep the
returned dict keys identical** (`TopScorer(**r)`) so `npm run gen:api` shows **no drift**.

**Tests:** backend tests are **flat under `tests/`** (CLAUDE.md's `tests/dashboard` path is stale).
Stats coverage: `tests/test_fixp1_stats.py` (extend; add a `top_scorers` case asserting Vick 2010 wk10
= 63.32 on the fixture DB). Frontend: `web/src/features/stats/stats.test.tsx` + the Home card.

**Doc sections to read (only these):** `07_PAGES_AND_VIEWS.md:186-190` (Stats explorer) + `:22-25`
(Home top-scorers), `05_API_CONTRACT.md:113-114` (endpoint shapes), `04_ANALYTICS_MODEL.md:34`
(season-totals read pattern). Gate commands: see `CLAUDE.md` → Commands.

## 6. Done when
- Stats → Top Scorers shows Vick 2010 wk10 = **63.32** (= player/matchup/NFL.com).
- No benched/unrostered performance appears as a league/team/owner record anywhere.
- Player-centric views show rostered-ever players' lines with year-matched bonuses; never-rostered NFL
  players are absent.
- Green gate; click-through on Stats, a player page, a matchup; `PROGRESS.md` updated.
- F-27 / config-ledger entry updated with the seed-bonus-rules + re-score + 0.1 validation gate.
