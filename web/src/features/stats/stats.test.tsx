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
    { player_id: 3, name_full: "Justin Jefferson", position: "WR", nfl_team: "MIN", season_year: 2017, week: null, points: 58 },
    { player_id: 1, name_full: "Lamar Jackson", position: "QB", nfl_team: "BAL", season_year: 2017, week: null, points: 53.5 },
  ],
};

const SEASON_TOTALS = {
  season_year: 2017,
  position: null,
  totals: [
    { player_id: 3, name_full: "Justin Jefferson", position: "WR", nfl_team: "MIN", total_points: 58, weeks_played: 2 },
  ],
};

function routeByPath(path: string) {
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
});
