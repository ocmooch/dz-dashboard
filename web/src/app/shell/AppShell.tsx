import { NavLink, Outlet } from "react-router-dom";

import { DataAsOf } from "./DataAsOf";
import { useSeasons } from "./SeasonContext";

// Left nav = the product's primary IA. `ready` items are built; the rest route to
// honest placeholders and carry a "soon" tag until their milestone lands.
const NAV: { to: string; label: string; ready?: boolean }[] = [
  { to: "/", label: "Home", ready: true },
  { to: "/standings", label: "Standings", ready: true },
  { to: "/matchups", label: "Matchups", ready: true },
  { to: "/managers", label: "Managers" },
  { to: "/rivalries", label: "Rivalries" },
  { to: "/records", label: "Records", ready: true },
  { to: "/players", label: "Players" },
  { to: "/draft", label: "Draft", ready: true },
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
            {s.is_scored ? "" : " · not scored"}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Global-search placeholder. The typeahead is wired in P10; until then this is a
 *  visible, honestly-disabled affordance so the IA reads correctly. */
function SearchPlaceholder() {
  return (
    <button
      type="button"
      className="dz-search"
      disabled
      title="Global search — lands in a later milestone"
      aria-label="Global search (coming soon)"
    >
      <span aria-hidden>⌕</span>
      <span>Search managers, players, seasons…</span>
      <kbd>/</kbd>
    </button>
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

        <SearchPlaceholder />

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
