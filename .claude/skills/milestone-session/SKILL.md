---
name: milestone-session
description: Use at the start of any Claude Code session that works on a Phase 2 milestone (P0–P11 in docs/09_ROADMAP.md) for the dz-dashboard repo. Governs how to enter the milestone cheaply — what to read, in what order, and when to stop — so a single milestone does not exhaust the context window. Trigger whenever a session begins with "milestone P{N}", "continue Phase 2", "work on the dashboard", or similar.
---

# Milestone session (token-cheap)

A milestone is split into **PLAN → BUILD → VERIFY**, each ideally its own thread, handed off
through files on disk. Pick the mode that matches the request and follow only that section.

## Entry (all modes) — ~3 cheap reads, then stop reading

1. `PROGRESS.md` — current state, what's next, the handful of files that matter now.
2. The single `P{N}` row in `docs/09_ROADMAP.md` — scope + "Done when".
3. If a plan exists: `docs/plans/P{N}-*.md`. If not and you're in PLAN mode, you'll write it.

Do **not** re-read the full design package, `PHASE2_KICKOFF.md`, or browse `analytics/` and
`web/` to "understand the current state" — that's what `PROGRESS.md` is for. Read additional
doc **sections** only when a specific task needs them (see the doc map in `CLAUDE.md`).

## PLAN mode

Read only the doc sections the milestone cites (CLAUDE.md doc map; e.g. P5 → 04 §3 + 05/07).
Write `docs/plans/P{N}-{name}.md` containing:

- Scope + the verbatim "Done when".
- Files to create/touch (paths).
- For each metric: function signature + the known-answer test cases (incl. a gap case).
- For each endpoint: route + response shape (name the schema; don't paste the whole contract).
- For each view: which existing primitives compose it.
- The test list (unit / contract / component / e2e) per `08`.

Commit the plan. **Write no implementation.** This session should end far under the limit.

## BUILD mode

Read the plan + `PROGRESS.md` + only the cited doc sections. Then implement:

- Hold the boundaries (CLAUDE.md hard rules): no DB writes, no math in `web/`, no hand-edited
  generated client, no fake zeros.
- Iterate against the **one** test file for the module you're on, quiet:
  `uv run pytest tests/dashboard/test_<module>.py -q`. Don't run the full suite each loop.
- Append progress to `PROGRESS.md` as files land.
- **Stop-early rule:** if context feels tight (large diffs, many files open, long tool logs),
  commit a checkpoint, write the precise next step into `PROGRESS.md`, and end the session.
  Resume fresh. A clean checkpoint always beats a truncated, limit-killed session.

## VERIFY mode

Use the `green-gate` skill. Fix only what fails. Do the manual click-through for the new
view(s). Update `PROGRESS.md` (mark the P# done, set the next P#) and commit with the
`AI-Model` / `Prompted-By` / `Reviewed-By` trailers. Never `Co-Authored-By: Claude`.

## Never (token traps)

- Opening `package-lock.json`, `uv.lock`, `web/src/lib/api/schema.d.ts`, or anything under
  `node_modules/`, `.venv/`, `web/dist/`, reports/coverage dirs.
- Pasting full passing test/lint output back into the conversation.
- Re-reading a doc already read this session.
