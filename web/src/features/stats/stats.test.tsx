import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StatsPage } from "./StatsPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

const seasonMock = vi.fn();
vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => seasonMock(),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const TOP_SCORERS = {
  season_year: 2017,
  week: null,
  position: null,
  scorers: [
    {
      player_id: 3,
      name_full: "Justin Jefferson",
      position: "WR",
      nfl_team: "MIN",
      season_year: 2017,
      week: null,
      points: 58,
    },
    {
      player_id: 1,
      name_full: "Lamar Jackson",
      position: "QB",
      nfl_team: "BAL",
      season_year: 2017,
      week: null,
      points: 53.5,
    },
  ],
};

const SEASON_TOTALS = {
  season_year: 2017,
  position: null,
  totals: [
    {
      player_id: 3,
      name_full: "Justin Jefferson",
      position: "WR",
      nfl_team: "MIN",
      total_points: 58,
      weeks_played: 2,
    },
  ],
};

const team = (id: number, name: string) => ({ team_id: id, team_name: name, owner_id: id, owner_name: name });
const SLEEPER_MARKET = {
  season_id: 1,
  season_year: 2026,
  is_faab_era: true,
  budget: 100,
  failed_bids_capability: { state: "available", note: null },
  teams: [
    { team: team(1, "Ice"), spent: 7, pct_of_budget: 0.07, winning_bids: 1, failed_bids: 0, largest_bid: 7 },
    {
      team: team(2, "Goose"),
      spent: 0,
      pct_of_budget: 0,
      winning_bids: 0,
      failed_bids: 1,
      largest_bid: null,
    },
  ],
  top_bids: [{ week: 4, team: team(1, "Ice"), player: { player_id: 68, player_name: "Hot Pickup" }, bid: 7 }],
  bid_wars: [
    {
      week: 4,
      player: { player_id: 68, player_name: "Hot Pickup" },
      winner: team(1, "Ice"),
      winning_bid: 7,
      margin: 3,
      bids: [
        { team: team(1, "Ice"), bid: 7, won: true },
        { team: team(2, "Goose"), bid: 4, won: false, failure_reason: "claimed by another owner" },
      ],
    },
  ],
};
let market: unknown = SLEEPER_MARKET;

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}/faab-market") return envelope(market);
  if (path === "/v1/stats/top-scorers") return envelope(TOP_SCORERS);
  if (path === "/v1/stats/season-totals") return envelope(SEASON_TOTALS);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StatsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  market = SLEEPER_MARKET;
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
  seasonMock.mockReturnValue({
    current: { season_id: 1, season_year: 2017, is_scored: true },
    seasons: [{ season_id: 1, season_year: 2017, is_scored: true }],
    setSeasonId: vi.fn(),
    isLoading: false,
  });
});

afterEach(() => vi.clearAllMocks());

describe("StatsPage", () => {
  it("defaults to season totals with deep links to player detail", async () => {
    renderPage();
    await screen.findByText("Justin Jefferson");
    expect(await screen.findByText("Season Totals")).toBeInTheDocument();
    expect(screen.getByText("58.00")).toBeInTheDocument();
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/players/3");
    expect(link).toBeDefined();
    expect(get.mock.calls.some((c) => c[0] === "/v1/stats/season-totals")).toBe(true);
  });

  it("keeps weekly leaders reachable from the tabs", async () => {
    renderPage();
    await screen.findByText("Justin Jefferson");
    await userEvent.click(screen.getByRole("tab", { name: "Top scorers" }));
    await waitFor(() => {
      expect(get.mock.calls.some((c) => c[0] === "/v1/stats/top-scorers")).toBe(true);
    });
    expect(await screen.findByText("Top Scorers")).toBeInTheDocument();
  });

  it("surfaces the gap for an unscored season", async () => {
    seasonMock.mockReturnValue({
      current: { season_id: 9, season_year: 2026, is_scored: false },
      seasons: [{ season_id: 9, season_year: 2026, is_scored: false }],
      setSeasonId: vi.fn(),
      isLoading: false,
    });
    get.mockImplementation((path: string) => {
      if (path === "/v1/stats/season-totals")
        return Promise.resolve(envelope({ ...SEASON_TOTALS, season_year: 2026, totals: [] }));
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    expect(
      await screen.findByText(/per-player fantasy scoring isn't available for this season/i),
    ).toBeInTheDocument();
  });

  it("FAAB market tab shows spend and bid wars", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "FAAB market" }));
    expect(await screen.findByText("Bid wars")).toBeInTheDocument();
    expect(screen.getAllByText("Hot Pickup").length).toBeGreaterThan(0);
    expect(screen.getByText("won by $3")).toBeInTheDocument();
    expect(screen.getByText("FAAB spend")).toBeInTheDocument();
  });

  it("FAAB market shows the shared failed-bids gap on a legacy season", async () => {
    seasonMock.mockReturnValue({
      current: { season_id: 1, season_year: 2017, is_scored: true, platform: "nfl_com" },
      seasons: [],
      setSeasonId: vi.fn(),
      isLoading: false,
    });
    market = {
      ...SLEEPER_MARKET,
      failed_bids_capability: { state: "not_on_platform", note: null },
      bid_wars: [],
      teams: SLEEPER_MARKET.teams.map((t) => ({ ...t, failed_bids: null })),
    };
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "FAAB market" }));
    expect(await screen.findByText("NFL.com didn't record unsuccessful waiver bids.")).toBeInTheDocument();
  });

  it("FAAB market marks a waiver-priority season as not applicable", async () => {
    market = { ...SLEEPER_MARKET, is_faab_era: false, teams: [], top_bids: [], bid_wars: [] };
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: "FAAB market" }));
    expect(await screen.findByText("Waiver priority era")).toBeInTheDocument();
  });
});
