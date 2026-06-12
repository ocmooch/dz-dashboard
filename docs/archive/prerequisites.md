# Prerequisites — Things to confirm/do before Phase 2 kickoff

> **⚠️ Archived (historical).** These are the pre-build prerequisites, completed before Phase 2
> started. The data-readiness outcome is recorded in [`P0_DATA_READINESS.md`](P0_DATA_READINESS.md);
> the live operational playbook is [`../PHASE2_RUNBOOK.md`](../PHASE2_RUNBOOK.md). Kept for provenance.

Phase 2 has far fewer human-only blockers than Phase 1 (no cookies, no secrets). The work
here is mostly **confirming Phase 1 is in the state Phase 2 assumes**, plus installing the
frontend toolchain.

Estimated time: **15–30 minutes** (most of it is letting the Phase 1 reconstruction finish, if
it hasn't).

---

## 1. Confirm Phase 1 data readiness (the big one)

Phase 2 builds views directly on Phase 1's tables. Two things must be true:

1. **Historical reconstruction has run.** At handoff, Phase 1's reconstruction code was
   complete and tested but the full run was pending (item C5). Run it if not done:
   ```bash
   cd ~/danger-zone                  # the Phase 1 repo
   uv run ff-pipeline reconstruct --start 2010 --end 2025   # ~2 hrs; resumable
   uv run ff-pipeline rescore --season 2016                 # repeat 2016..2025 if needed
   uv run ff-pipeline verify --sweep --season 2024          # spot-check the bar
   ```
2. **Coverage matches `docs/03_DATA_ACCESS.md`.** Quick sanity probe:
   ```bash
   sqlite3 data/fantasy.db "SELECT 'scored', COUNT(*) FROM player_stats_scored;
     SELECT 'seasons w/ champion', COUNT(*) FROM seasons WHERE champion_team_id IS NOT NULL;
     SELECT 'matchups', COUNT(*) FROM matchups;
     SELECT DISTINCT season_year FROM player_stats_scored ORDER BY 1;"
   ```
   You should see scored rows for 2016–2025, champions set per completed season, and matchups
   across all weeks (not just week 1).

> If reconstruction is still running, you can still start Phase 2 milestones **P1–P4** — they
> use already-solid data (players, stats, owner records). Box scores (P5) wait for it.

## 2. Note the database location

Phase 2's BFF reads the same SQLite file. Confirm the path (from Phase 1's `.env`):
```bash
grep DATABASE_URL ~/danger-zone/.env   # e.g. sqlite:///./data/fantasy.db
```
Write it down — the BFF settings will point at it (read-only).

## 3. Confirm the Phase 1 toolchain is current

Phase 2's backend lives in the same repo and reuses Phase 1's Python tooling:
```bash
cd ~/danger-zone
python3 --version    # 3.11+
uv --version
uv sync              # deps current
```

## 4. Install the frontend toolchain

Phase 2 adds a `web/` SPA. You need Node.js (LTS) and npm:
```bash
# Install Node 20 LTS if you don't have it (nvm recommended)
node --version    # v20.x or newer
npm --version
```
(If you prefer pnpm or bun, note it — the kickoff defaults to npm.)

## 5. Decide the things in `docs/10_OPEN_QUESTIONS.md`

Skim `10_OPEN_QUESTIONS.md` and jot answers to at least the **sign-off** items:
- Q1 data-access architecture (default: BFF) — confirm.
- Q2 frontend stack — confirm or swap.
- Q3 visual direction (default: "Danger Zone" HUD) — confirm or redirect.
- Q4 view priority — confirm or reorder.
- Q5 standings tiebreaker — provide your league's actual order.
- Q7 starting-lineup slot config — confirm where it lives / provide it.

These shape the first milestones; having them decided avoids rework.

## 6. Branch

Same git model as Phase 1. Cut a feature branch from `dev`:
```bash
cd ~/dz-dashboard
git checkout dev && git pull
git checkout -b feature/phase-2-dashboard
```

---

## You're ready when…

- [ ] Phase 1 reconstruction has run (or you accept starting with P1–P4 only)
- [ ] `player_stats_scored` has rows for 2016–2025; matchups span all weeks
- [ ] You know the `DATABASE_URL` / DB file path
- [ ] `uv sync` is clean; `node`/`npm` installed
- [ ] You've answered the sign-off questions in `10_OPEN_QUESTIONS.md`
- [ ] You're on a `feature/phase-2-*` branch cut from `dev`

Now open `PHASE2_KICKOFF.md`.
