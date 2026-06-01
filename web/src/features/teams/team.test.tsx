import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TeamPage } from "./TeamPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const OVERVIEW = {
  team_id: 10,
  team_name: "Iceman 2017",
  season_id: 1,
  season_year: 2017,
  owner_id: 5,
  owner_name: "Iceman",
  rank: 1,
  rank_basis: "computed",
  wins: 2,
  losses: 0,
  ties: 0,
  points_for: 235,
  points_against: 225,
  final_rank: null,
  made_playoffs: null,
  is_champion: false,
  is_scored: true,
};

const ROSTER = {
  team_id: 10,
  season_year: 2017,
  week: 1,
  weeks_available: [1, 2],
  is_scored: true,
  players: [
    { player_id: 1, player_name: "Ice QB One", position: "QB", nfl_team: "BAL", roster_slot: "QB", is_starter: true, league_points: 24, acquisition_type: "draft", acquisition_week: 1 },
    { player_id: 2, player_name: "Ice D/ST", position: "DEF", nfl_team: "PIT", roster_slot: "DEF", is_starter: true, league_points: null, acquisition_type: "draft", acquisition_week: 1 },
  ],
};

const SCHEDULE = {
  team_id: 10,
  season_year: 2017,
  games: [
    { matchup_id: 100, week: 1, is_playoff: false, opponent_team_id: 11, opponent_team_name: "Goose 2017", opponent_owner_name: "Goose", team_score: 130, opponent_score: 125, result: "W", margin: 5 },
  ],
};

const TREND = {
  team_id: 10,
  season_year: 2017,
  is_scored: true,
  points: [
    { week: 1, team_score: 130, league_avg: 133.85, is_playoff: false },
    { week: 2, team_score: 105, league_avg: 113.75, is_playoff: false },
  ],
};

const TRANSACTIONS = { team_id: 10, season_year: 2017, transactions: [] };

function routeByPath(path: string) {
  if (path === "/v1/teams/{team_id}") return envelope(OVERVIEW);
  if (path === "/v1/teams/{team_id}/roster") return envelope(ROSTER);
  if (path === "/v1/teams/{team_id}/schedule") return envelope(SCHEDULE);
  if (path === "/v1/teams/{team_id}/scoring-trend") return envelope(TREND);
  if (path === "/v1/teams/{team_id}/transactions") return envelope(TRANSACTIONS);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/teams/10"]}>
        <Routes>
          <Route path="/teams/:teamId" element={<TeamPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("TeamPage", () => {
  it("renders the season header with record and rank", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Iceman 2017" });
    expect(screen.getByText("Rank")).toBeInTheDocument();
    expect(screen.getByText("235.0")).toBeInTheDocument(); // points for
  });

  it("renders the roster with a DST gap instead of a zero", async () => {
    renderPage();
    await screen.findByText("Ice QB One");
    const gap = screen.getByText(/No scored data/i);
    expect(gap).toBeInTheDocument();
    expect(gap.textContent).not.toMatch(/\b0\b/);
  });

  it("renders the schedule with a box-score deep link", async () => {
    renderPage();
    await screen.findByText(/vs Goose/i);
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/matchups/100");
    expect(link).toBeDefined();
  });

  it("renders the scoring-trend chart vs league average", async () => {
    renderPage();
    expect(
      await screen.findByLabelText(/Team score vs league average by week/i),
    ).toBeInTheDocument();
  });

  it("shows an empty state when there are no transactions", async () => {
    renderPage();
    expect(await screen.findByText(/No transactions/i)).toBeInTheDocument();
  });
});
