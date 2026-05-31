import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DraftPage } from "./DraftPage";

// The SPA reaches data only through the generated client; mocking it keeps these
// as pure presentation tests — no network, no business logic under test.
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

const pick = (over: number, name: string, owner: string, pts: number, value: number) => ({
  overall: over,
  round: 1,
  pick_in_round: over,
  team_id: over,
  team_name: `${owner} 2016`,
  owner_id: over,
  owner_name: owner,
  player_id: over * 10,
  player_name: name,
  position: "RB",
  season_year: 2016,
  season_points: pts,
  value,
  available: true,
  reason: null,
});

const KELCE = pick(1, "Travis Kelce", "Iceman", 22, -13.67);
const CMC = pick(4, "Christian McCaffrey", "Maverick", 55, 8.33);

const BOARD = {
  season_id: 2,
  season_year: 2016,
  available: true,
  reason: null,
  num_teams: 4,
  rounds: [
    {
      round: 1,
      picks: [KELCE, pick(2, "Lamar Jackson", "Goose", 48, 7.5), pick(3, "Justin Jefferson", "Slider", 37, -3.5), CMC],
    },
  ],
};

const VALUE = {
  season_id: 2,
  season_year: 2016,
  available: true,
  reason: null,
  definition: "Pick value = a player's regular-season fantasy points minus the slot average.",
  slot_window: 2,
  picks: [CMC, pick(2, "Lamar Jackson", "Goose", 48, 7.5), pick(3, "Justin Jefferson", "Slider", 37, -3.5), KELCE],
  steals: [CMC],
  busts: [KELCE],
};

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}/draft") return envelope(BOARD);
  if (path === "/v1/seasons/{season_id}/draft/value") return envelope(VALUE);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/draft"]}>
        <DraftPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("DraftPage", () => {
  it("renders the draft board with picks deep-linking to players", async () => {
    renderPage();
    await screen.findByText("Round 1");
    expect(screen.getAllByText("Christian McCaffrey").length).toBeGreaterThan(0);
    expect(screen.getByText("Lamar Jackson")).toBeInTheDocument();
    // Each pick card links to the drafted player.
    const links = screen.getAllByRole("link");
    expect(links.some((a) => a.getAttribute("href") === "/players/40")).toBe(true);
  });

  it("identifies steals and busts with signed value", async () => {
    renderPage();
    await screen.findByText("Steals");
    expect(screen.getByText("Busts")).toBeInTheDocument();
    // The steal carries a positive value, the bust a negative one.
    expect(screen.getAllByText("+8.33").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-13.67").length).toBeGreaterThan(0);
  });

  it("labels a season whose draft was never captured, never inventing picks", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(
          envelope({
            season_id: 2,
            season_year: 2016,
            available: false,
            reason: "draft_not_captured",
            num_teams: null,
            rounds: [],
          }),
        );
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    expect(await screen.findByText(/Draft not captured for this season/i)).toBeInTheDocument();
    expect(screen.queryByText("Round 1")).not.toBeInTheDocument();
  });
});
