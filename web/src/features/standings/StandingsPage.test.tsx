import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StandingsPage } from "./StandingsPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 2, season_year: 2016, is_scored: true },
    seasons: [{ season_id: 2, season_year: 2016, is_scored: true }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const STANDINGS = {
  season_id: 2,
  season_year: 2016,
  rank_basis: "final_rank",
  tiebreak_caveat: null,
  rows: [
    {
      rank: 1,
      team_id: 10,
      team_name: "Iceman 2016",
      owner_id: 1,
      owner_name: "Iceman",
      wins: 11,
      losses: 3,
      ties: 0,
      points_for: 1600,
      points_against: 1400,
      win_pct: 0.786,
      streak: { result: "W", length: 3 },
      final_rank: 1,
    },
    {
      rank: 2,
      team_id: 11,
      team_name: "Goose 2016",
      owner_id: 2,
      owner_name: "Goose",
      wins: 9,
      losses: 5,
      ties: 0,
      points_for: 1500,
      points_against: 1450,
      win_pct: 0.643,
      streak: { result: "L", length: 1 },
      final_rank: 2,
    },
  ],
};

const TIMELINE = {
  season_id: 2,
  season_year: 2016,
  teams: [],
};

const ROBBED = {
  team_id: 11,
  owner_id: 2,
  owner_name: "Goose",
  team_name: "Goose 2016",
  actual_wins: 9,
  all_play_win_pct: 0.78,
  expected_wins: 11.2,
  luck_delta: -2.2,
  points_for_rank: 2,
  standings_rank: 2,
};
const BLESSED = {
  team_id: 10,
  owner_id: 1,
  owner_name: "Iceman",
  team_name: "Iceman 2016",
  actual_wins: 11,
  all_play_win_pct: 0.6,
  expected_wins: 8.6,
  luck_delta: 2.4,
  points_for_rank: 1,
  standings_rank: 1,
};

const INSIGHTS = {
  season_id: 2,
  season_year: 2016,
  through_week: 14,
  available: true,
  reason: null,
  most_robbed: ROBBED,
  most_blessed: BLESSED,
  teams: [BLESSED, ROBBED],
};

const INSIGHTS_GAP = {
  season_id: 3,
  season_year: 2026,
  through_week: 0,
  available: false,
  reason: "no_completed_matchups",
  most_robbed: null,
  most_blessed: null,
  teams: [],
};

let insightsResponse: unknown = INSIGHTS;

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}/standings") return envelope(STANDINGS);
  if (path === "/v1/seasons/{season_id}/standings/timeline") return envelope(TIMELINE);
  if (path === "/v1/seasons/{season_id}/standings/insights") return envelope(insightsResponse);
  if (path === "/v1/seasons/{season_id}/conferences") return envelope({ available: false, conferences: [] });
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StandingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  insightsResponse = INSIGHTS;
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("StandingsPage", () => {
  it("surfaces completed-season final placement from final_rank", async () => {
    renderPage();
    expect(await screen.findByText("Champion")).toBeInTheDocument();
    expect(screen.getByText("2nd")).toBeInTheDocument();
    expect(screen.getByText("Finish")).toBeInTheDocument();
  });

  it("voices the most-robbed and most-blessed callouts and links them to manager profiles", async () => {
    renderPage();
    expect(await screen.findByText("Robbed")).toBeInTheDocument();
    expect(screen.getByText("Blessed")).toBeInTheDocument();
    // The robbed callout deep-links to its manager profile.
    const robbed = screen.getByText("Robbed").closest("a");
    expect(robbed).toHaveAttribute("href", "/managers/2");
    const blessed = screen.getByText("Blessed").closest("a");
    expect(blessed).toHaveAttribute("href", "/managers/1");
  });

  it("shows a DataGap (never a 0) when schedule-luck is unavailable", async () => {
    insightsResponse = INSIGHTS_GAP;
    renderPage();
    // Card title still renders; the body degrades to the gap affordance.
    expect(await screen.findByText("Robbed & Blessed")).toBeInTheDocument();
    expect(screen.queryByText("Robbed")).not.toBeInTheDocument();
    expect(screen.queryByText("Blessed")).not.toBeInTheDocument();
  });
});
