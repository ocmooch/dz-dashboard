import { NavLink, Outlet } from "react-router-dom";

import { DataAsOf } from "./DataAsOf";
import { useSeasons } from "./SeasonContext";

const NAV: { to: string; label: string; ready?: boolean }[] = [
  { to: "/", label: "Home", ready: true },
  { to: "/standings", label: "Standings", ready: true },
  { to: "/records", label: "Records", ready: true },
  { to: "/rivalries", label: "Rivalries" },
  { to: "/managers", label: "Managers" },
  { to: "/players", label: "Players" },
  { to: "/matchups", label: "Matchups" },
  { to: "/draft", label: "Draft" },
];

function SeasonSwitcher() {
  const { seasons, current, setSeasonId } = useSeasons();
  return (
    <label className="flex items-center gap-2">
      <span className="dz-eyebrow">Season</span>
      <select
        value={current?.season_id ?? ""}
        onChange={(e) => setSeasonId(Number(e.target.value))}
        className="num rounded-sm border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-text"
      >
        {seasons.map((s) => (
          <option key={s.season_id} value={s.season_id}>
            {s.season_year}
            {s.is_scored ? "" : " (unscored)"}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-[var(--border)] bg-[color-mix(in_oklab,var(--bg)_85%,transparent)] px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <span
            className="grid h-9 w-9 place-items-center rounded border border-accent font-display text-[var(--fs-h3)] font-bold text-accent"
            style={{ background: "var(--accent-quiet)" }}
          >
            DZ
          </span>
          <div className="leading-tight">
            <div className="font-display text-[var(--fs-h3)] font-bold tracking-[0.18em] text-text">
              DANGER&nbsp;ZONE
            </div>
            <div className="dz-eyebrow">league analytics</div>
          </div>
        </div>
        <div className="flex items-center gap-5">
          <SeasonSwitcher />
          <DataAsOf />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1200px] flex-1 gap-6 px-5 py-6">
        <nav className="hidden w-44 shrink-0 flex-col gap-1 md:flex" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                [
                  "rounded-sm px-3 py-2 text-[var(--fs-sm)] transition-colors",
                  isActive
                    ? "bg-[var(--accent-quiet)] font-semibold text-accent"
                    : "text-muted hover:bg-[var(--surface-2)] hover:text-text",
                ].join(" ")
              }
            >
              {item.label}
              {!item.ready && <span className="ml-2 align-middle text-[var(--fs-xs)] text-faint">soon</span>}
            </NavLink>
          ))}
        </nav>

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
