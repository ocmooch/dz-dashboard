# Sleeper Era — dashboard planning set

The league moved from NFL.com (defunct) to Sleeper for 2026. The **program plan is canonical in
danger-zone**: `../danger-zone/docs/sleeper/00_SLEEPER_ERA_MASTER_PLAN.md` — read its §1–§5 first.

| Doc | What it covers |
|-----|----------------|
| [00_UPSTREAM_STATE.md](00_UPSTREAM_STATE.md) | **Read first.** What danger-zone S1–S8 actually delivered: data location + go-live gating, read helpers, capability semantics, 2026 row shapes, user decisions, dashboard hotspots, fixtures |
| [01_DASHBOARD_ARCHITECTURE.md](01_DASHBOARD_ARCHITECTURE.md) | BFF + SPA design: provenance, capabilities, contract additions, cross-era aggregation rules |
| [02_DASHBOARD_BUILD_PLAN.md](02_DASHBOARD_BUILD_PLAN.md) | Milestones D0–D8, each gated on a danger-zone milestone |
| [03_CROSS_PLATFORM_UX.md](03_CROSS_PLATFORM_UX.md) | Visual/UX rules so both eras read as one product |

Upstream docs to read by section only: `../danger-zone/docs/sleeper/01_PIPELINE_ARCHITECTURE.md`
§5 (schema), §8.3 (capabilities), §9.1 (read helpers); `04_SLEEPER_FIELD_MAPPING.md` for field meaning.
