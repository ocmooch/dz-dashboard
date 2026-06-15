# Proposal — the per-manager epithet (§3B stretch, NOT yet shipped)

**Status:** reviewable proposal only; **not retained in code** after VERIFY because
the real-DB assignment pass was too noisy and product-owner sign-off was not
granted. Nothing here is wired into `owner_story()`, the `/v1/owners/{id}/story`
endpoint, or `ManagerStory.tsx`. Ship only after explicit sign-off on the
vocabulary, voice, thresholds, and assignment density.

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

The proposed fingerprint would carry these inputs:

| field | source |
|-------|--------|
| `seasons_played`, `championships`, `runner_ups`, `best_finish` | `owners.owner_career` / season finishes |
| `win_pct` | career W/(W+L+T) |
| `best_luck_delta` / `worst_luck_delta` | max / min single-season all-play `luck_delta` |

## Vocabulary + thresholds (priority order; first match wins)

A gate applies first: **`seasons_played ≥ MIN_EPITHET_SEASONS (3)`** — a one/two-season
manager has no story yet and gets nothing.

| # | Label | Fires when |
|---|-------|-----------|
| 1 | **The Dynasty** | `championships ≥ 3` |
| 2 | **The Bridesmaid** | `championships == 0` and `runner_ups ≥ 2` |
| 3 | **The Powerhouse** | `championships == 0` and `win_pct ≥ 0.60` |
| 4 | **The Lucky Devil** | best season `luck_delta ≥ +2.0` |
| 5 | **The Snakebitten** | worst season `luck_delta ≤ −2.0` |

Each yields `{label, blurb}`; the blurb is a short, affectionate sentence. Thresholds
are tuned for full-season real-DB history (the fixture's 2-week seasons can't fire the
luck bars, so those are tested in isolation against constructed fingerprints).

VERIFY note (2026-06-15): applying this proposal to the real DB assigned 12 managers,
mostly via **The Lucky Devil**. That fails the "earned, not noisy" bar, so the helper
was removed from the branch rather than kept without sign-off.

Assigned under the withdrawn thresholds:

| Manager | Assigned label | Triggering evidence |
|---------|----------------|---------------------|
| harry | The Snakebitten | worst `luck_delta = -3.91` |
| scott | The Lucky Devil | best `luck_delta = +3.18` |
| mike | The Lucky Devil | best `luck_delta = +2.91` |
| sully | The Lucky Devil | best `luck_delta = +2.18` |
| DJ | The Dynasty | 4 championships |
| Dave | The Lucky Devil | best `luck_delta = +2.27` |
| Gregg | The Lucky Devil | best `luck_delta = +2.45` |
| Chris | The Lucky Devil | best `luck_delta = +2.73` |
| Jeff | The Lucky Devil | best `luck_delta = +2.09` |
| Rob | The Dynasty | 3 championships |
| Jimbo | The Lucky Devil | best `luck_delta = +2.09` |
| Cheese | The Lucky Devil | best `luck_delta = +2.64` |

## Open questions for the product owner

1. Is the vocabulary affectionate enough? Any labels to drop/rename/add?
2. Are the bars strict enough that an assigned epithet always feels *earned*?
3. Where should it render — a chip beside the manager's name, or a line inside the
   "Your Story" band?
4. Should the real-DB pass surface how many of the current ~12 managers would get one
   (too many → it's noise; too few → it's a dead feature)?
