import { NavLink, Outlet } from "react-router-dom";

import { GlobalSearch } from "@/features/search/GlobalSearch";

import { DataAsOf } from "./DataAsOf";
import { useSeasons } from "./SeasonContext";

// Left nav = the product's primary IA. `ready` items are built; the rest route to
// honest placeholders and carry a "soon" tag until their milestone lands.
const NAV: { to: string; label: string; ready?: boolean }[] = [
  { to: "/", label: "Home", ready: true },
  { to: "/seasons", label: "Seasons", ready: true },
  { to: "/managers", label: "Managers", ready: true },
  { to: "/standings", label: "Standings", ready: true },
  { to: "/playoffs", label: "Playoffs", ready: true },
  { to: "/matchups", label: "Matchups", ready: true },
  { to: "/rivalries", label: "Rivalries", ready: true },
  { to: "/records", label: "Records", ready: true },
  { to: "/rules", label: "Rules & Eras", ready: true },
  { to: "/stories", label: "Stories", ready: true },
  { to: "/players", label: "Players", ready: true },
  { to: "/stats", label: "Stats", ready: true },
  { to: "/draft", label: "Draft", ready: true },
  { to: "/about", label: "About Data", ready: true },
];

function SeasonSwitcher() {
  const { seasons, current, setSeasonId } = useSeasons();
  return (
    <label className="dz-season">
      <span className="dz-season-label">Season</span>
      <select
        aria-label="Season"
        value={current?.season_id ?? ""}
        onChange={(e) => setSeasonId(Number(e.target.value))}
        className="dz-season-select"
      >
        {seasons.map((s) => (
          <option key={s.season_id} value={s.season_id}>
            {s.season_year}
            {s.is_scored ? "" : " · no player scoring"}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="dz-topbar">
        <div className="dz-brand">
          <span className="dz-brand-mark">DZ</span>
          <div className="leading-none">
            <div className="dz-brand-name">Danger&nbsp;Zone</div>
            <div className="dz-brand-sub">league analytics</div>
          </div>
        </div>

        <GlobalSearch />

        <div className="dz-topbar-right">
          <SeasonSwitcher />
          <DataAsOf />
        </div>
      </header>

      <div className="dz-layout">
        <nav className="dz-nav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `dz-nav-item ${isActive ? "active" : ""}`.trim()}
            >
              <span className="label-text">{item.label}</span>
              {!item.ready && <span className="dz-soon">soon</span>}
            </NavLink>
          ))}
        </nav>

        <main className="dz-main min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
