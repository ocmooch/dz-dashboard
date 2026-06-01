import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerDetailPage } from "./PlayerDetailPage";
import { PlayersPage } from "./PlayersPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 1, season_year: 2017, is_scored: true },
    seasons: [{ season_id: 1, season_year: 2017, is_scored: true }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const PLAYER_INDEX = {
  limit: 50,
  offset: 0,
  players: [
    { player_id: 1, name_full: "Lamar Jackson", position: "QB", nfl_team: "BAL" },
    { player_id: 2, name_full: "Christian McCaffrey", position: "RB", nfl_team: "SF" },
  ],
};

const PLAYER_OUT = {
  player_id: 1,
  name_full: "Lamar Jackson",
  position: "QB",
  nfl_team: "BAL",
  is_active: true,
  rookie_year: 2018,
  gsis_id: "G1",
};

const SCORING = {
  player_id: 1,
  season_year: 2017,
  available: true,
  total_points: 53.5,
  weeks: [
    { week: 1, points: 35.5, breakdown: {} },
    { week: 2, points: 18, breakdown: {} },
  ],
};

const OWNERSHIP = {
  player_id: 1,
  events: [
    { team_id: 10, team_name: "Iceman 2017", season_year: 2017, week: 1, roster_slot: "QB", acquisition_type: "draft" },
  ],
};

const AVAILABILITY_GAP = {
  player_id: 1,
  season_year: 2017,
  available: false,
  reason: "availability_history_not_reconstructable",
  weeks: [],
};

function routeByPath(path: string) {
  if (path === "/v1/players") return envelope(PLAYER_INDEX);
  if (path === "/v1/players/{player_id}") return envelope(PLAYER_OUT);
  if (path === "/v1/players/{player_id}/scoring") return envelope(SCORING);
  if (path === "/v1/players/{player_id}/ownership") return envelope(OWNERSHIP);
  if (path === "/v1/players/{player_id}/availability") return envelope(AVAILABILITY_GAP);
  throw new Error(`unexpected path ${path}`);
}

function renderWithProviders(ui: React.ReactNode, initialPath = "/players") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/players" element={ui} />
          <Route path="/players/:playerId" element={ui} />
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

describe("PlayersPage", () => {
  it("renders the player index with deep links to detail", async () => {
    renderWithProviders(<PlayersPage />);
    await screen.findByText("Lamar Jackson");
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/players/1");
    expect(link).toBeDefined();
    expect(screen.getByText("Christian McCaffrey")).toBeInTheDocument();
  });

  it("passes the position filter to the API query", async () => {
    renderWithProviders(<PlayersPage />);
    await screen.findByText("Lamar Jackson");
    await userEvent.selectOptions(screen.getByLabelText("Filter by position"), "QB");
    await waitFor(() => {
      const calls = get.mock.calls.filter((c) => c[0] === "/v1/players");
      expect(calls.some((c) => (c[1] as any).params.query.position === "QB")).toBe(true);
    });
  });

  it("shows an empty state when no players match", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/v1/players") return Promise.resolve(envelope({ ...PLAYER_INDEX, players: [] }));
      return Promise.resolve(routeByPath(path));
    });
    renderWithProviders(<PlayersPage />);
    expect(await screen.findByText(/no players match/i)).toBeInTheDocument();
  });
});

describe("PlayerDetailPage", () => {
  it("renders metadata, IDs, and the weekly scoring chart", async () => {
    renderWithProviders(<PlayerDetailPage />, "/players/1");
    await screen.findByRole("heading", { name: "Lamar Jackson" });
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText(/GSIS:/)).toBeInTheDocument();
    // The chart's accessible title proves the scoring series rendered.
    expect(await screen.findByLabelText(/Weekly league points — 2017/i)).toBeInTheDocument();
  });

  it("renders availability as a DataGap for a non-reconstructable season", async () => {
    renderWithProviders(<PlayerDetailPage />, "/players/1");
    await screen.findByRole("heading", { name: "Lamar Jackson" });
    expect(await screen.findByText(/Availability — current season only/i)).toBeInTheDocument();
  });

  it("links ownership events to the owning team's page", async () => {
    renderWithProviders(<PlayerDetailPage />, "/players/1");
    await screen.findByText("Iceman 2017");
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/teams/10");
    expect(link).toBeDefined();
  });
});
