# Handoff → danger-zone (ff-pipeline): capture FAAB bid amounts

> **STATUS: COMPLETE (2026-06-21).** Upstream capture landed — `extra_data.faab_bid` is populated
> on `waiver_add` legs for 2021–2025 (214/241/214/205/182 rows; pre-2021 null). The dashboard
> consume side shipped on `feature/faab-bid-display`: `_faab_bid()` now reads a `$0` bid as a real
> free claim (the old `or`-chain dropped `0`), and the winning bid renders as its own `"$X FAAB"`
> pill in the team transactions log. Verified live (team 1 / 2025). The remaining-budget analytic
> in §"After data lands" remains the deferred follow-on milestone.


**Repo:** `/home/mainuser/danger-zone`  ·  **DB:** `data/fantasy.db` (SQLite)
**Authored:** 2026-06-20, against the live DB.  ·  **Tracks:** dz-dashboard `F-37`.
**Context:** There is an underserved need to surface FAAB (Free Agent Acquisition Budget) data in
the dz-dashboard `/teams/` view — FAAB spending in the transactions log, remaining budget per week.
The league adopted FAAB in **2021** (before that: waiver priority). The dashboard is read-only and
already **wired to consume** a bid (see "Dashboard is ready", below), but the source value was never
ingested. This handoff asks you to capture it upstream. **Until it lands, no dashboard FAAB display
can be built** — spend and remaining-budget both derive from the bid.

Do **not** change any read-API response *shapes*; this is data-population work behind existing
columns. The preferred storage target is the existing `transactions.extra_data` JSON.

## The data reality (measured against `data/fantasy.db`, 2026-06-20)

Bids are **absent, not sparse** — this is a capture gap, not an identity/coverage gap. Numbers
reproduce with the queries inline.

| Fact | Evidence | Value |
|------|----------|-------|
| No bid anywhere in `transactions` | `SELECT COUNT(*) FROM transactions WHERE lower(extra_data) LIKE '%faab%' OR lower(extra_data) LIKE '%bid%' OR lower(extra_data) LIKE '%budget%';` | **3** — and all 3 are `setting_change` rows (below), zero are add/waiver legs |
| `waiver_add` carry no extra_data | `SELECT extra_data, COUNT(*) FROM transactions WHERE transaction_type='waiver_add' GROUP BY 1;` | `null` × 3139, `''` × 2 |
| `free_agent_add` carry no extra_data | same, type `free_agent_add` | `null` × 3468, `''` × 52 |
| `waiver_priority_used` never populated | `SELECT waiver_priority_used IS NULL, COUNT(*) FROM transactions GROUP BY 1;` | NULL for **all 41,870** rows (pre-2021 priority also never captured) |
| FAAB-era `waiver_add` rows exist | per-year counts 2021–2025 | 214 / 241 / 214 / 205 / 182 — so the *fact* of each claim is present, just not the bid |

The **only** FAAB facts present are 3 `setting_change` rows (`extra_data.description`):

- 2021 — `"Chris changed Waiver Type from 'Resets to Inverse Standings Order' to 'Waiver Budget'"`
- 2021 — `"Chris changed Waiver Budget to '100'"`  ← the $100 league default
- 2022 — `"Dan changed Ice Station Zebra Waiver Budget from '39' to '76'"`  ← a per-team mid-season bump

These are already classified T1/T2 by the dashboard's `analytics/league_changes.py` and surface in
`/seasons/`. They give the **budget**, not the **spend**.

## The work

### 1. Source-availability check — FIRST, gate everything else on it

**Do not assume the bid is scrapeable.** Confirm whether NFL.com exposes the winning FAAB bid amount
on a page the crawler can reach for the FAAB-era seasons (2021–2025):

- The paginated history transactions page already swept by
  `src/ff_pipeline/crawlers/nfl_com/transactions.py` (`sweep_transactions`) — does a `waiver_add`
  row carry the winning bid in any cell? **Capture a real sample HTML row** and confirm.
- If it is not on that page, identify the alternate source (waiver report / league budget / per-claim
  detail page), whether it is fetchable, and whether it joins back to a transaction leg
  (by player + effective week + team, or an NFL.com txn id).
- **Record the finding.** If the bid is genuinely unavailable from any NFL.com surface for these
  seasons, **stop and report that** — the dashboard then documents `faab_bid:null` as a permanent
  true source gap (closing F-37's open question) and this handoff ends here.

### 2. Parser change (only if §1 confirms availability)

Capture the bid in the add/waiver-add branch of the row parser:

- `src/ff_pipeline/crawlers/nfl_com/parsers.py` — `_parse_transaction_row` (≈ line 1083), the
  "Add / Waiver-add" leg (≈ lines 1167–1179, where the player goes *To* a team).
- Extract the bid into the existing `ParsedTransaction.extra_data` field (≈ line 162) as
  `{"faab_bid": <int|float>}`.
- Gate naturally on presence: a row with a bid stores it; pre-2021 rows have no bid and stay null.
  **No hardcoded year in the parser.**

**Storage decision.** Prefer `extra_data["faab_bid"]` — zero schema/migration cost, and the
dashboard's `_faab_bid()` already reads exactly this key (and falls back to `faab` / `bid`). Only
promote to a first-class `transactions.faab_bid` column if you want it queryable/indexed; that adds
an alembic migration and is **optional**, not required for the dashboard to light up.

### 3. Re-crawl + re-ingest

- Re-run the transactions sweep + ingest for **2021–2025** so existing rows gain `faab_bid`. The
  runner that resolves parsed rows and upserts is `crawlers/nfl_com/league.run_nfl_com` (per the
  `transactions.py` module docstring).
- The sweep already de-dupes legs by `_leg_key` (`(nfl_transaction_id, type, player, direction,
  executed_at)`); confirm the ingest **upserts in place** so the re-run updates rows rather than
  duplicating legs.
- **Scoring is untouched** — transactions don't feed scoring; no re-score needed.

### Done when

- A representative set of 2021–2025 `waiver_add` rows have a non-null `faab_bid` in `extra_data`
  matching the NFL.com-displayed winning bid (spot-check a handful by hand against the source page).
- Pre-2021 rows remain null (no FAAB era).
- **The dz-dashboard lights up with no dashboard code change** — verify by hitting
  `/v1/teams/{team_id}/transactions` for a 2021+ team and seeing `faab_bid` populated. (If you chose
  the optional first-class column instead of `extra_data`, tell the dashboard owner so `_faab_bid()`
  can be pointed at it — that *is* a small additive dashboard step.)

## Dashboard is ready (no change needed for the data to surface)

The consume path already exists; this is why upstream capture alone unblocks display:

- `src/ff_dashboard/analytics/teams.py` — `_faab_bid()` reads `extra_data.{faab_bid,faab,bid}`
  (≈ lines 418–428); `team_transactions()` already emits `faab_bid` per row.
- `src/ff_dashboard/api/schemas.py` — `TeamTransaction.faab_bid: float | None` is in the contract.
- `web/src/features/teams/TeamPage.tsx` — `transactionDetail()` renders `"$X FAAB"` when non-null,
  and never renders `0`/`$0` for a missing bid.

## After data lands — dashboard work (BUILT)

1. **Transactions log** — ✅ DONE (PR #91): `$0` read as a real claim; bid renders as a `"$X FAAB"` pill.
2. **Remaining-budget analytic** — ✅ DONE (`feature/faab-remaining-budget`): `team_faab_budget()` in
   `analytics/teams.py` derives per-week `remaining = budget_at_week − cumulative spend` from captured
   `faab_bid`s. FAAB-era is data-driven on the presence of captured bids (not a hardcoded year).
   Season budget = flat **$100** base + mid-season per-team **credits** (the budget `setting_change`
   events carry `team_id=NULL`, matched by the name in the description; modeled as timestamped credits
   so Ice Station Zebra 2022's +$37 refund reproduces — remaining never negative). Endpoint
   `GET /v1/teams/{team_id}/faab-budget`; `FaabBudgetCard` on the Team page (self-hides for pre-FAAB
   seasons). Overspend guard renders honestly rather than a negative.
3. **Honest gap** — ✅ pre-FAAB seasons show no card (not-applicable, not `$0`); a `$0` spend week is a
   real value; an unattributable overspend is flagged, never a fake balance.
