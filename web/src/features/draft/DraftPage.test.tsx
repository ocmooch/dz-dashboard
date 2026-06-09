import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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

const pick = (
  over: number,
  name: string,
  owner: string,
  pts: number,
  value: number,
  round = 1,
  pickInRound = over,
) => ({
  overall: over,
  round,
  pick_in_round: pickInRound,
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
const ROUND_TWO = [
  pick(5, "Saquon Barkley", "Maverick", 50, 6.5, 2, 1),
  pick(6, "Ja'Marr Chase", "Slider", 44, 4.5, 2, 2),
  pick(7, "Josh Allen", "Goose", 47, 3.5, 2, 3),
  pick(8, "Amon-Ra St. Brown", "Iceman", 42, 1.5, 2, 4),
];

const BOARD = {
  season_id: 2,
  season_year: 2016,
  available: true,
  reason: null,
  num_teams: 12,
  rounds: [
    {
      round: 1,
      picks: [KELCE, pick(2, "Lamar Jackson", "Goose", 48, 7.5), pick(3, "Justin Jefferson", "Slider", 37, -3.5), CMC],
    },
    {
      round: 2,
      picks: ROUND_TWO,
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
    expect(screen.getByTitle("Christian McCaffrey")).toBeInTheDocument();
    expect(screen.getByTitle("Lamar Jackson")).toBeInTheDocument();
    // Each pick card links to the drafted player.
    const links = screen.getAllByRole("link");
    expect(links.some((a) => a.getAttribute("href") === "/players/40")).toBe(true);
  });

  it("renders rounds as a 12-column snake board", async () => {
    renderPage();
    const roundOne = await screen.findByLabelText("Round 1 snake picks");
    expect(roundOne).toHaveStyle({ gridTemplateColumns: "repeat(12, minmax(0, 1fr))" });

    const roundTwo = screen.getByLabelText("Round 2 snake picks");
    const picks = within(roundTwo).getAllByRole("link");
    expect(picks[0]).toHaveAttribute("title", "Amon-Ra St. Brown");
    expect(picks[picks.length - 1]).toHaveAttribute("title", "Saquon Barkley");
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
