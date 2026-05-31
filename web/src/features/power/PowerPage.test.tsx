import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PowerPage } from "./PowerPage";

// Reach data only through the generated client; mocking it keeps this a pure
// presentation test — no network, no business logic under test.
const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 3, season_year: 2017, is_scored: true },
    seasons: [{ season_id: 3, season_year: 2017, is_scored: true }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const row = (
  rank: number,
  owner: string,
  power: number,
  delta: number,
  standingsRank: number,
) => ({
  rank,
  team_id: rank,
  team_name: `${owner} 2017`,
  owner_id: rank,
  owner_name: owner,
  wins: 2,
  losses: 0,
  ties: 0,
  points_for: 260,
  power_score: power,
  points_for_per_game: 130,
  win_pct: 1,
  recent_points_for_per_game: 130,
  z_points_for: 1.2,
  z_win_pct: 1.0,
  z_recent: 1.1,
  standings_rank: standingsRank,
  rank_delta: delta,
});

const POWER = {
  season_id: 3,
  season_year: 2017,
  through_week: 2,
  regular_season_weeks: 2,
  weights: { points_for_per_game: 0.5, win_pct: 0.3, recent_points_for_per_game: 0.2 },
  explainer: "Power score blends three within-season z-scores per the documented weights.",
  // Iceman is rated one spot above his record (a riser); Goose one below (a faller).
  rows: [row(1, "Iceman", 1.54, 1, 2), row(2, "Goose", -0.32, -1, 1)],
};

const TIMELINE = {
  season_id: 3,
  season_year: 2017,
  regular_season_weeks: 2,
  teams: [
    { team_id: 1, team_name: "Iceman 2017", owner_name: "Iceman", points: [
      { week: 1, rank: 2, power_score: 0.4 },
      { week: 2, rank: 1, power_score: 1.54 },
    ] },
    { team_id: 2, team_name: "Goose 2017", owner_name: "Goose", points: [
      { week: 1, rank: 1, power_score: 0.8 },
      { week: 2, rank: 2, power_score: -0.32 },
    ] },
  ],
};

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}/power") return envelope(POWER);
  if (path === "/v1/seasons/{season_id}/power/timeline") return envelope(TIMELINE);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/power"]}>
        <PowerPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("PowerPage", () => {
  it("renders the ranking table with power scores in order", async () => {
    renderPage();
    // Owner names also appear in the chart's data-table fallback, so match ≥1.
    expect((await screen.findAllByText("Iceman")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Goose").length).toBeGreaterThan(0);
    // Power scores are surfaced (only in the ranking table).
    expect(screen.getByText("1.54")).toBeInTheDocument();
    expect(screen.getByText("-0.32")).toBeInTheDocument();
  });

  it("shows the model-vs-standings movement (riser ▲ / faller ▼)", async () => {
    renderPage();
    await screen.findAllByText("Iceman");
    expect(screen.getByText(/▲ 1/)).toBeInTheDocument();
    expect(screen.getByText(/▼ 1/)).toBeInTheDocument();
  });

  it("carries the 'how this is computed' explainer", async () => {
    renderPage();
    expect(await screen.findByText(/How this is computed/i)).toBeInTheDocument();
    expect(screen.getByText(/within-season z-scores/i)).toBeInTheDocument();
  });

  it("renders the power-over-time chart with its accessible title", async () => {
    renderPage();
    expect(
      await screen.findByLabelText("Power ranking by week (rank 1 on top)"),
    ).toBeInTheDocument();
  });
});
