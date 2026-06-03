---
name: green-gate
description: Use when verifying a dz-dashboard milestone before commit, or any time the user asks to "run the gate", "run the tests", "check it's green", lint, typecheck, or confirm a milestone's "Done when". Runs the backend + frontend checks in a token-cheap way — quiet flags, output to files, and reading only failures — so a passing gate costs almost no context and a failing one surfaces just the error.
---

# Green gate (read only what fails)

The gate is the single noisiest thing in a session. Run it quietly, send verbose output to
files, and pull only failures into context. A fully green gate should add a few lines, not
a few thousand.

## Backend (repo root)

```bash
uv run pytest tests -q > /tmp/pytest.log 2>&1; echo "pytest exit=$?"; tail -n 15 /tmp/pytest.log
uv run ruff check -q && uv run ruff format --check && echo "ruff: clean"
uv run mypy src/ff_dashboard > /tmp/mypy.log 2>&1; echo "mypy exit=$?"; tail -n 15 /tmp/mypy.log
```

Read-only / write-safety check (must return nothing):
```bash
git grep -nE "INSERT|UPDATE |DELETE |upsert|crawler|normalizer" src/ff_dashboard
```

## Frontend (in `web/`, P3+)

```bash
npm run gen:api && git diff --exit-code web/src/lib/api && echo "contract: no drift"
npm run typecheck > /tmp/tsc.log 2>&1; echo "tsc exit=$?"; tail -n 20 /tmp/tsc.log
npm run test > /tmp/vitest.log 2>&1; echo "vitest exit=$?"; tail -n 20 /tmp/vitest.log
```

e2e is slow and very noisy — VERIFY session only, and only when the milestone calls for it:
```bash
npm run test:e2e > /tmp/e2e.log 2>&1; echo "e2e exit=$?"; tail -n 30 /tmp/e2e.log
```

## Reading results

- If `exit=0` / "clean" / "no drift": state it in one line. **Do not** print the log.
- If non-zero: `grep -nE "FAILED|Error|error:" /tmp/<log>` (or open just the failing test
  file at the relevant line range). Fix, then re-run only that one check, scoped to the file:
  `uv run pytest tests/test_<x>.py -q`.
- Never `cat` a whole log into the conversation.

## Done

All checks green + the `P{N}` "Done when" in `docs/09_ROADMAP.md` satisfied + manual
click-through done → update `PROGRESS.md`, commit with `AI-Model` / `Prompted-By` /
`Reviewed-By` trailers.
