# Proposal — the per-manager epithet (§3B stretch, NOT yet shipped)

**Status:** reviewable proposal awaiting product-owner sign-off on the vocabulary
and voice. The code exists (`analytics/owner_story.assign_epithet`) and is tested,
but it is **deliberately not wired** into `owner_story()`, the `/v1/owners/{id}/story`
endpoint, or `ManagerStory.tsx`. Ship only after sign-off (the VERIFY session).

## Why it's gated

The epithet is the highest-ceiling / highest-taste-risk element in §3B: a one-line
*archetype* derived from a manager's statistical fingerprint. Done well it's the most
screenshot-able content in the app; done carelessly it's noise or feels unfair about
a real person. So it follows the plan's non-negotiable guardrails:

- Assigned **only** when the data strongly and unambiguously supports it (a documented
  threshold per archetype). If no archetype clears its bar, the owner gets **no
  epithet** — never a forced or generic one.
- A small, fixed, **affectionate** vocabulary — celebratory or wry, never cruel.
- Reviewed by the product owner before it ships.

## The fingerprint

`OwnerFingerprint` (in `analytics/owner_story.py`) carries the inputs:

| field | source |
|-------|--------|
| `seasons_played`, `championships`, `runner_ups`, `best_finish` | `owners.owner_career` / season finishes |
| `win_pct` | career W/(W+L+T) |
| `best_luck_delta` / `worst_luck_delta` | max / min single-season all-play `luck_delta` |

## Vocabulary + thresholds (priority order; first match wins)

A gate applies first: **`seasons_played ≥ MIN_EPITHET_SEASONS (3)`** — a one/two-season
manager has no story yet and gets nothing.

| # | Label | Fires when | Constant |
|---|-------|-----------|----------|
| 1 | **The Dynasty** | `championships ≥ 3` | `EPITHET_DYNASTY_TITLES` |
| 2 | **The Bridesmaid** | `championships == 0` and `runner_ups ≥ 2` | `EPITHET_BRIDESMAID_RUNNERUPS` |
| 3 | **The Powerhouse** | `championships == 0` and `win_pct ≥ 0.60` | `EPITHET_CONTENDER_WINPCT` |
| 4 | **The Lucky Devil** | best season `luck_delta ≥ +2.0` | `EPITHET_LUCKY_DELTA` |
| 5 | **The Snakebitten** | worst season `luck_delta ≤ −2.0` | `EPITHET_ROBBED_DELTA` |

Each yields `{label, blurb}`; the blurb is a short, affectionate sentence. Thresholds
are tuned for full-season real-DB history (the fixture's 2-week seasons can't fire the
luck bars, so those are tested in isolation against constructed fingerprints).

Tests: `tests/test_owner_story.py` — each archetype fires at its threshold and does
**not** fire just below it; the tenure gate and the "title disqualifies Bridesmaid"
rule are covered.

## Open questions for the product owner

1. Is the vocabulary affectionate enough? Any labels to drop/rename/add?
2. Are the bars strict enough that an assigned epithet always feels *earned*?
3. Where should it render — a chip beside the manager's name, or a line inside the
   "Your Story" band?
4. Should the real-DB pass surface how many of the current ~12 managers would get one
   (too many → it's noise; too few → it's a dead feature)?
