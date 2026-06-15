import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BoxScorePage } from "./BoxScorePage";
import { MatchupsPage } from "./MatchupsPage";

// The SPA reaches data only through the generated client; mocking it keeps these
// as pure presentation tests — no network, no business logic under test.
const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

// Pin the active season so we don't depend on SeasonProvider's load timing.
vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 1, season_year: 2017, is_scored: true },
    seasons: [{ season_id: 1, season_year: 2017, is_scored: true }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const SEASON_SUMMARY = { season_id: 1, season_year: 2017, regular_season_weeks: 14, playoff_weeks: 3 };

const WEEK_GAMES = {
  season_id: 1,
  season_year: 2017,
  week: 1,
  is_scored: true,
  games: [
    {
      matchup_id: 712,
      is_playoff: false,
      team_a: { team_id: 10, team_name: "Iceman 2017", owner_name: "Iceman", score: 130, is_winner: true },
      team_b: { team_id: 11, team_name: "Goose 2017", owner_name: "Goose", score: 125, is_winner: false },
      margin: 5,
      is_close: false,
      is_blowout: false,
      winner_team_id: 10,
    },
    {
      matchup_id: 713,
      is_playoff: false,
      team_a: { team_id: 12, team_name: "Mav 2017", owner_name: "Maverick", score: 160.4, is_winner: true },
      team_b: { team_id: 13, team_name: "Viper 2017", owner_name: "Viper", score: 120, is_winner: false },
      margin: 40.4,
      is_close: false,
      is_blowout: true,
      winner_team_id: 12,
    },
  ],
};

const BOX = {
  matchup_id: 712,
  season_year: 2017,
  week: 1,
  available: true,
  is_playoff: false,
  winner_team_id: 10,
  home: {
    team_id: 10,
    team_name: "Iceman 2017",
    owner_name: "Iceman",
    total_score: 130,
    starter_points: 104,
    bench_points: 51,
    optimal_total: 117,
    points_left_on_bench: 13,
    beat_projection_by: null,
    lineup: [
      {
        roster_slot: "QB",
        player_id: 1,
        player_name: "Ice QB One",
        position: "QB",
        league_points: 24,
        is_starter: true,
        breakdown: { passing: 24 },
        projection: null,
        projection_delta: null,
        lineup_value: null,
        available: true,
        reason: null,
      },
      {
        roster_slot: "DEF",
        player_id: 2,
        player_name: "Ice D/ST",
        position: "DEF",
        league_points: null,
        is_starter: true,
        breakdown: {},
        projection: null,
        available: false,
        reason: "team_defense_not_scored",
      },
      {
        roster_slot: "BN",
        player_id: 3,
        player_name: "Ice QB Two",
        position: "QB",
        league_points: 26,
        is_starter: false,
        breakdown: { passing: 26 },
        projection: null,
        available: true,
        reason: null,
      },
    ],
  },
  away: {
    team_id: 11,
    team_name: "Goose 2017",
    owner_name: "Goose",
    total_score: 125,
    starter_points: 125,
    bench_points: 10,
    optimal_total: 125,
    points_left_on_bench: 0,
    beat_projection_by: null,
    lineup: [
      {
        roster_slot: "QB",
        player_id: 4,
        player_name: "Goose QB",
        position: "QB",
        league_points: 30,
        is_starter: true,
        breakdown: { passing: 30 },
        projection: null,
        available: true,
        reason: null,
      },
    ],
  },
};

function renderWithProviders(ui: React.ReactNode, initialPath = "/matchups") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/matchups" element={ui} />
          <Route path="/matchups/:matchupId" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}") return envelope(SEASON_SUMMARY);
  if (path === "/v1/seasons/{season_id}/weeks/{week}/matchups") return envelope(WEEK_GAMES);
  if (path === "/v1/matchups/{matchup_id}/box-score") return envelope(BOX);
  throw new Error(`unexpected path ${path}`);
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("MatchupsPage", () => {
  it("renders one card per deduped game with the winner's score emphasized", async () => {
    renderWithProviders(<MatchupsPage />);
    const ice = await screen.findByText("Iceman 2017");
    expect(ice).toBeInTheDocument();
    expect(screen.getByText("Goose 2017")).toBeInTheDocument();
    // Two games -> two box-score deep links.
    const links = screen.getAllByRole("link");
    expect(links.filter((a) => a.getAttribute("href")?.startsWith("/matchups/"))).toHaveLength(2);
    expect(screen.getByText("130.00")).toBeInTheDocument();
  });

  it("shows the blowout margin badge on a lopsided game", async () => {
    renderWithProviders(<MatchupsPage />);
    await screen.findByText("Mav 2017");
    expect(screen.getByText(/blowout/i)).toBeInTheDocument();
  });

  it("colors each side's margin with a signed winner and loser value", async () => {
    renderWithProviders(<MatchupsPage />);
    await screen.findByText("Iceman 2017");
    expect(screen.getByText("+5.00")).toHaveClass("text-win");
    expect(screen.getByText("-5.00")).toHaveClass("text-loss");
  });

  it("deep-links each card to its box score", async () => {
    renderWithProviders(<MatchupsPage />);
    await screen.findByText("Iceman 2017");
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/matchups/712");
    expect(link).toBeDefined();
  });

  it("steps the week and refetches for the new week", async () => {
    renderWithProviders(<MatchupsPage />);
    await screen.findByText("Iceman 2017");
    await userEvent.click(screen.getByRole("button", { name: "Next week" }));
    await waitFor(() => {
      const matchupCalls = get.mock.calls.filter(
        (c) => c[0] === "/v1/seasons/{season_id}/weeks/{week}/matchups",
      );
      expect(matchupCalls.some((c) => (c[1] as any).params.path.week === 2)).toBe(true);
    });
  });

  it("surfaces an unscored-season gap badge instead of faking scores", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/weeks/{week}/matchups")
        return Promise.resolve(envelope({ ...WEEK_GAMES, is_scored: false }));
      return Promise.resolve(routeByPath(path));
    });
    renderWithProviders(<MatchupsPage />);
    // The affordance scopes the gap to per-player scoring for the season, and is
    // year-agnostic (the pre-2016 reconstruction has landed; F-51) — it never
    // labels the team-level grid incomplete.
    const banner = await screen.findByText(/per-player fantasy scoring isn't available for this season/i);
    expect(banner).toBeInTheDocument();
  });
});

describe("BoxScorePage", () => {
  it("renders both teams with starter/optimal/bench/left-on-bench stats", async () => {
    renderWithProviders(<BoxScorePage />, "/matchups/712");
    await screen.findByText("Iceman 2017");
    expect(screen.getByText("Goose 2017")).toBeInTheDocument();
    expect(screen.getAllByText("Starters").length).toBeGreaterThan(0);
    expect(screen.getByText("104.00")).toBeInTheDocument(); // home starters
    expect(screen.getByText("117.00")).toBeInTheDocument(); // home optimal
    expect(screen.getByText("13.00")).toBeInTheDocument(); // points left on bench
  });

  it("renders a DST starter as a DataGap, never a zero", async () => {
    renderWithProviders(<BoxScorePage />, "/matchups/712");
    await screen.findByText("Ice D/ST");
    const gap = screen.getByText(/team defense not scored/i);
    expect(gap).toBeInTheDocument();
    expect(gap.textContent).not.toMatch(/\b0\b/);
  });

  it("separates bench players from starters", async () => {
    renderWithProviders(<BoxScorePage />, "/matchups/712");
    await screen.findByText("Ice QB Two");
    expect(screen.getByText("bench")).toBeInTheDocument();
  });

  it("shows an unscored-season box score as a gap, not zeros", async () => {
    get.mockImplementation(() =>
      Promise.resolve(
        envelope({
          matchup_id: 99,
          season_year: 2026,
          week: 1,
          available: false,
          reason: "season_unscored",
          is_playoff: false,
          home: null,
          away: null,
          winner_team_id: null,
        }),
      ),
    );
    renderWithProviders(<BoxScorePage />, "/matchups/99");
    expect(
      await screen.findByText(/Per-player scoring not available for this season/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View week 1 matchups/i })).toHaveAttribute(
      "href",
      "/matchups?week=1",
    );
  });

  it("labels did-not-play zeroes as Out, not a data gap", async () => {
    get.mockImplementation(() =>
      Promise.resolve(
        envelope({
          matchup_id: 77,
          season_year: 2017,
          week: 5,
          available: true,
          is_playoff: false,
          winner_team_id: 20,
          home: {
            team_id: 20,
            team_name: "Maverick 2017",
            owner_name: "Maverick",
            total_score: 100,
            starter_points: 100,
            bench_points: 0,
            optimal_total: 100,
            points_left_on_bench: 0,
            beat_projection_by: null,
            lineup: [
              {
                roster_slot: "IR",
                player_id: 30,
                player_name: "Hurt Hero",
                position: "WR",
                league_points: 0,
                is_starter: false,
                breakdown: {},
                projection: null,
                projection_delta: null,
                available: true,
                reason: null,
                zero_reason: "did_not_play",
                zero_detail: null,
              },
              {
                roster_slot: "BN",
                player_id: 31,
                player_name: "Bye Week Body",
                position: "RB",
                league_points: 0,
                is_starter: false,
                breakdown: {},
                projection: null,
                projection_delta: null,
                available: true,
                reason: null,
                zero_reason: "did_not_play",
                zero_detail: null,
              },
            ],
          },
          away: null,
        }),
      ),
    );
    renderWithProviders(<BoxScorePage />, "/matchups/77");
    const irRow = (await screen.findByText("Hurt Hero")).closest("tr")!;
    const irCells = within(irRow).getAllByRole("cell");
    expect(irCells[irCells.length - 1]).toHaveTextContent("Out");
    const byeRow = screen.getByText("Bye Week Body").closest("tr")!;
    const byeCells = within(byeRow).getAllByRole("cell");
    expect(byeCells[byeCells.length - 1]).toHaveTextContent("Out");
    // Neither is the amber honesty/data-gap affordance.
    expect(screen.queryByText(/Data not available/i)).not.toBeInTheDocument();
  });

  it("uses the signed value color without repeating hit or miss copy", async () => {
    get.mockImplementation(() =>
      Promise.resolve(
        envelope({
          ...BOX,
          home: {
            ...BOX.home,
            lineup: [
              {
                ...BOX.home.lineup[0],
                projection: 20,
                projection_delta: 4,
                lineup_value: "starter_hit",
              },
              {
                ...BOX.home.lineup[1],
                projection: 3,
                projection_delta: -3,
                lineup_value: "starter_miss",
              },
            ],
          },
        }),
      ),
    );
    renderWithProviders(<BoxScorePage />, "/matchups/712");

    const positive = await screen.findByText("+4.00");
    const negative = await screen.findByText("-3.00");
    expect(positive).toHaveClass("text-win");
    expect(negative).toHaveClass("text-loss");
    expect(screen.queryByText("hit")).not.toBeInTheDocument();
    expect(screen.queryByText("miss")).not.toBeInTheDocument();
  });

  it("explains a 0 by context: bye / DNP label, an unexpected flag, or a bare 0", async () => {
    get.mockImplementation(() =>
      Promise.resolve(
        envelope({
          matchup_id: 88,
          season_year: 2022,
          week: 14,
          available: true,
          is_playoff: false,
          winner_team_id: 40,
          home: {
            team_id: 40,
            team_name: "Zeroes 2022",
            owner_name: "Zed",
            total_score: 0,
            starter_points: 0,
            bench_points: 0,
            optimal_total: 0,
            points_left_on_bench: 0,
            beat_projection_by: null,
            lineup: [
              {
                roster_slot: "WR",
                player_id: 50,
                player_name: "Bye Guy",
                position: "WR",
                league_points: 0,
                is_starter: true,
                breakdown: {},
                projection: null,
                available: true,
                reason: null,
                zero_reason: "bye",
                zero_detail: null,
              },
              {
                roster_slot: "WR",
                player_id: 51,
                player_name: "Scratch Guy",
                position: "WR",
                league_points: 0,
                is_starter: true,
                breakdown: {},
                projection: null,
                available: true,
                reason: null,
                zero_reason: "did_not_play",
                zero_detail: null,
              },
              {
                roster_slot: "WR",
                player_id: 52,
                player_name: "Mismatch Guy",
                position: "WR",
                league_points: 0,
                is_starter: true,
                breakdown: {},
                projection: null,
                available: true,
                reason: null,
                zero_reason: "unexpected",
                zero_detail: "nflverse credits 8 pts but the league scored 0 — likely a scratch.",
              },
              {
                roster_slot: "WR",
                player_id: 53,
                player_name: "Goose Egg",
                position: "WR",
                league_points: 0,
                is_starter: true,
                breakdown: {},
                projection: null,
                available: true,
                reason: null,
                zero_reason: null,
                zero_detail: null,
              },
            ],
          },
          away: null,
        }),
      ),
    );
    renderWithProviders(<BoxScorePage />, "/matchups/88");

    const ptsCell = async (name: string) => {
      const row = (await screen.findByText(name)).closest("tr")!;
      const cells = within(row).getAllByRole("cell");
      return cells[cells.length - 1];
    };

    expect(await ptsCell("Bye Guy")).toHaveTextContent("Bye");
    expect(await ptsCell("Scratch Guy")).toHaveTextContent("Out");
    expect(await ptsCell("Mismatch Guy")).toHaveTextContent("⚠");
    // The clean played-0 shows a bare number with no status tag or warning.
    const clean = await ptsCell("Goose Egg");
    expect(clean).toHaveTextContent("0");
    expect(clean).not.toHaveTextContent(/Bye|Out|⚠/);
  });

  it("emphasizes the winning team's total score", async () => {
    renderWithProviders(<BoxScorePage />, "/matchups/712");
    await screen.findByText("Iceman 2017");
    const winnerScore = screen.getByText("130.00");
    expect(winnerScore).toHaveClass("text-win");
    // The loser's total appears muted (other 125.00s are stat values, not the header).
    expect(screen.getAllByText("125.00").some((el) => el.classList.contains("text-muted"))).toBe(true);
  });
});
