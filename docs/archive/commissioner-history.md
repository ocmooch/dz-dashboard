# Commissioner History — Plan

**Status:** PLAN (not started)
**Scope:** Phase 1 (danger-zone) data layer + Phase 2 (dz-dashboard) analytics / API / SPA
**Depends on:** league-history slice (already landed locally)

---

## Problem

Commissioner tenure is a first-class layer of league narrative — it defines eras, contextualizes
rules changes, and is a natural organizing axis for the league timeline. The data exists only in
people's heads. The DB has no `commissioners` table; the dashboard has no surface for it.
The 2-season term rule (often but not always followed) provides enough structure to reconstruct
the history, but the reconstruction needs human confirmation and a durable home.

---

## Data archaeology — what the DB already tells us

The league spans 2010–2025 (16 completed seasons). Founded with 10 owners; 18 have ever played.

| Season | Champion | Owner |
|--------|----------|-------|
| 2010 | Final Fantasy Football | Rob |
| 2011 | Papa Fies SteakhouseExperience | Chris |
| 2012 | Tainted Basil | DJ |
| 2013 | Roddy's White Walkers | scott |
| 2014 | The King in the Northvale | DJ |
| 2015 | Mint Chocolate Chip Kelly | DJ |
| 2016 | I Need Mo Allowance | DJ |
| 2017 | Brotherhood Without Bungalows | harry |
| 2018 | ROBJECTION | Rob |
| 2019 | Stevie Wonders Blindside Blitz | sully |
| 2020 | Shish Karob | Rob |
| 2021 | DuDu Shit-Pooster | scott |
| 2022 | CMC Rules Everything Around Me | sully |
| 2023 | Fred Jacksons Revenge | Gregg |
| 2024 | Putting the CAP in CHAMP | Dave |
| 2025 | Cream of the C | harry |

**One confirmed data point:** In 2016, Rob (owner_id=10) named his team "Commissioner J Gordon"
(per `analytics/historical_team_names.py`, year=2016, slot=10). This is strong evidence Rob held
the commissioner role in 2016. With 2-season terms, his tenure was likely 2016–2017.

**16 seasons ÷ 2 = ~8 commissioners.** Possible windows (broken occasionally per the user):

| Window | Expected commissioner | Evidence / confidence |
|--------|----------------------|-----------------------|
| 2010–2011 | ? | Founding season; likely a founding member |
| 2012–2013 | ? | Unknown |
| 2014–2015 | ? | Unknown |
| 2016–2017 | Rob | "Commissioner J Gordon" team name 2016 — HIGH |
| 2018–2019 | ? | Unknown |
| 2020–2021 | ? | Unknown |
| 2022–2023 | ? | Unknown |
| 2024–2025 | ? | Unknown |

**Action required before BUILD:** The user must fill in the `?` rows in the seed file below.
The plan proceeds with the infrastructure; the seed data drives everything downstream.

---

## Owners for reference (from DB)

| owner_id | display_name | joined | left |
|----------|-------------|--------|------|
| 1 | harry | 2010 | — |
| 2 | scott | 2010 | — |
| 3 | mike | 2010 | — |
| 4 | sully | 2010 | — |
| 5 | DJ | 2010 | — |
| 6 | Dave | 2010 | — |
| 7 | Gregg | 2010 | — |
| 8 | Chris | 2010 | — |
| 9 | Jeff | 2010 | — |
| 10 | Rob | 2010 | — |
| 11 | Jimbo | 2023 | — |
| 12 | Kofi | 2025 | — |
| 13 | Adam | 2010 | 2016 |
| 14 | Ill | 2010 | 2022 |
| 15 | Tom | 2012 | 2013 |
| 16 | George | 2014 | 2014 |
| 17 | Cheese | 2014 | 2024 |
| 18 | Kevin | 2015 | 2017 |

---

## Design decisions

### Where does the data live?

Commissioner history is **manually curated metadata** — like `owner_identity_overrides`, it
cannot be crawled from NFL.com. It belongs in a static seed file in danger-zone, loaded into a
new `commissioners` DB table via Alembic migration. This keeps the single-source-of-truth
principle intact and lets the dashboard read it read-only via the existing repository pattern.

### Schema

```sql
CREATE TABLE commissioners (
    commissioner_id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id       INTEGER NOT NULL REFERENCES leagues(league_id),
    owner_id        INTEGER NOT NULL REFERENCES owners(owner_id),
    from_year       INTEGER NOT NULL,
    to_year         INTEGER NOT NULL,   -- inclusive; NULL = current/ongoing
    notes           TEXT               -- optional human annotation
);
CREATE UNIQUE INDEX uq_commissioners_owner_from ON commissioners(league_id, owner_id, from_year);
```

`from_year`/`to_year` are NFL season years (e.g. 2016–2017 means those two fantasy seasons).
`to_year = NULL` means the tenure is ongoing (current commissioner). A commissioner who served
two non-consecutive terms gets two rows.

### Where does the seed data live in danger-zone?

`danger-zone/data/commissioner_history.yaml` — a human-editable YAML file, version-controlled.
The Alembic env or a standalone `load_static_data.py` script reads it and upserts rows.
Pattern mirrors `danger-zone/data/owner_identity_overrides.yaml` if one exists, or is new.

### Dashboard exposure

1. `analytics/commissioners.py` — pure `(session) → list[CommissionerTerm]` function, no
   FastAPI imports. Returns sorted terms with owner display name resolved.
2. Extend `/v1/league/overview` response: add `commissioners: list[CommissionerTerm]`.
3. Integrate into `/v1/league/timeline` events: commissioner transitions become timeline events
   with `type: "commissioner_change"`.
4. SPA: Commissioner timeline strip on the Seasons/League History page; commissioner badge on
   individual season cards; commissioner note on the manager profile page.

---

## Phase 1 changes (danger-zone)

### 1. Seed file — `data/commissioner_history.yaml`

```yaml
# Commissioner history — manually curated. from_year/to_year are inclusive NFL season years.
# Add notes for any term that broke the 2-season rule.
commissioners:
  - owner_id: 10    # Rob
    from_year: 2016
    to_year: 2017
    notes: "Team name 'Commissioner J Gordon' (2016) corroborates"

  # FILL IN REMAINING TERMS:
  # - owner_id: ?
  #   from_year: 2010
  #   to_year: 2011
  # - owner_id: ?
  #   from_year: 2012
  #   to_year: 2013
  # - owner_id: ?
  #   from_year: 2014
  #   to_year: 2015
  # - owner_id: ?
  #   from_year: 2018
  #   to_year: 2019
  # - owner_id: ?
  #   from_year: 2020
  #   to_year: 2021
  # - owner_id: ?
  #   from_year: 2022
  #   to_year: 2023
  # - owner_id: ?
  #   from_year: 2024
  #   to_year: 2025
```

### 2. Alembic migration — `commissioners` table

New revision in `danger-zone/alembic/versions/`. Creates the `commissioners` table and
`uq_commissioners_owner_from` index. No data; seed data is loaded separately.

### 3. Seed loader — `danger-zone/scripts/load_commissioner_history.py`

Reads `data/commissioner_history.yaml`, validates `owner_id`s against the DB, upserts
`commissioners` rows (INSERT OR REPLACE). Idempotent; safe to re-run.

### 4. Repository helper — `ff_pipeline/repository/queries.py`

Additive read-only function:

```python
def commissioner_terms(session: Session, league_id: int) -> list[Commissioner]:
    """Return commissioner terms ordered by from_year."""
    ...
```

Returns ORM `Commissioner` rows (or a lightweight dataclass if the ORM model approach
is too heavy for a new table).

---

## Phase 2 changes (dz-dashboard)

### 1. Analytics — `src/ff_dashboard/analytics/commissioners.py`

```python
@dataclass
class CommissionerTerm:
    owner_id: int
    owner_name: str
    from_year: int
    to_year: int | None
    seasons: int          # computed: (to_year - from_year + 1) or ongoing count
    notes: str | None

def commissioner_history(session: Session) -> list[CommissionerTerm]:
    """Return all commissioner terms, oldest first."""
    ...
```

Pure function; no FastAPI. Covered by a unit test with the fixture DB (stub rows).

### 2. Schema additions — `src/ff_dashboard/api/schemas.py`

```python
class CommissionerTerm(BaseModel):
    owner_id: int
    owner_name: str
    from_year: int
    to_year: int | None
    seasons: int
    notes: str | None

class LeagueOverview(BaseModel):
    ...existing fields...
    commissioners: list[CommissionerTerm]
```

### 3. Route update — `src/ff_dashboard/api/routes/league.py`

Extend the `/v1/league/overview` handler to call `commissioner_history(session)` and
include it in the response.

Extend the `/v1/league/timeline` handler: after computing existing timeline events, inject
`commissioner_change` events at the `from_year` of each term:

```python
{"year": term.from_year, "type": "commissioner_change",
 "description": f"{term.owner_name} becomes commissioner",
 "detail": f"Served {term.from_year}–{term.to_year or 'present'}"}
```

### 4. SPA — `web/src/features/league/`

**Commissioner timeline strip** — a compact horizontal timeline on the Seasons/League History
page, one node per commissioner. Matches the existing era/timeline visual language.

**Season card badge** — on each season card in the timeline, show a "Commish: [name]" badge
(derived by year lookup from the commissioners array returned by overview).

**Manager profile** — on `ManagerProfilePage.tsx`, if the manager has any commissioner terms,
show a "Commissioner" section: years served, total seasons.

**Home page** — optionally: a "Current commissioner" line in the league meta card.

---

## Test plan

| Test | Location |
|------|----------|
| `test_commissioner_history_unit.py` | `tests/dashboard/` — pure analytics function with stub DB rows |
| Add `CommissionerTerm` assertions to `test_p2_endpoints.py` league overview test | existing file |
| Manual: open `/league` page, verify commissioner strip renders | VERIFY session |
| Manual: open a manager profile for a commissioner (e.g. Rob), verify term shown | VERIFY session |

---

## Seed file path in danger-zone

`danger-zone/data/commissioner_history.yaml` — **needs user to fill in the gaps before BUILD.**

The seed is the gating dependency. Everything else (migration, queries, analytics, API,
frontend) can be built in parallel with seed authoring, but the dashboard cannot show real
data until the YAML is complete and loaded.

---

## Done when

- `commissioners` table exists in the DB with all terms populated.
- `GET /v1/league/overview` includes `commissioners: [...]` with all terms.
- `GET /v1/league/timeline` includes `commissioner_change` events.
- Commissioner strip renders on the League History page.
- Commissioner term shows on manager profile for any owner who served.
- Full gate green (backend pytest + ruff + mypy; frontend gen:api no-drift + typecheck + test).
- `PROGRESS.md` updated.

---

## Build order (within the milestone)

1. **User fills in `data/commissioner_history.yaml`** — gating.
2. **danger-zone:** Alembic migration → seed loader → `queries.commissioner_terms` → run seed.
3. **dashboard:** `analytics/commissioners.py` + unit test.
4. **dashboard:** Schema additions + `gen:api`.
5. **dashboard:** Route update (overview + timeline).
6. **dashboard:** Frontend commissioner strip + season badge + manager profile section.
7. **VERIFY session:** full gate + click-through.
