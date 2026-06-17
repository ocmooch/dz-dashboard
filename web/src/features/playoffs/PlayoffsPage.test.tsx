import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PlayoffsPage } from "./PlayoffsPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 1, season_year: 2015, is_scored: false },
    seasons: [{ season_id: 1, season_year: 2015, is_scored: false }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const BRACKET = {
  season_id: 1,
  season_year: 2015,
  regular_season_weeks: 13,
  available: true,
  reason: null,
  caveat:
    "Post-regular-season matchups from the source data. Championship versus consolation structure is shown only when source flags distinguish it.",
  consolation_distinguished: true,
  playoff_bracket: {
    size: 6,
    bye_teams: [
      { team_id: 1, team_name: "Slider 2015", owner_id: 1, owner_name: "Slider" },
    ],
    rounds: [
      {
        round_num: 1,
        round_label: "First Round",
        bye_teams: [{ team_id: 1, team_name: "Slider 2015", owner_id: 1, owner_name: "Slider" }],
        games: [
          {
            matchup_id: 10,
            is_playoff: true,
            is_consolation: false,
            game_label: null,
            winner_team_id: 2,
            team_a: { team_id: 2, team_name: "Maverick 2015", owner_id: 2, owner_name: "Maverick", score: 130, is_winner: true },
            team_b: { team_id: 3, team_name: "Goose 2015", owner_id: 3, owner_name: "Goose", score: 110, is_winner: false },
          },
        ],
      },
      {
        round_num: 2,
        round_label: "Semifinals",
        bye_teams: [],
        games: [
          {
            matchup_id: 20,
            is_playoff: true,
            is_consolation: false,
            game_label: null,
            winner_team_id: 1,
            team_a: { team_id: 1, team_name: "Slider 2015", owner_id: 1, owner_name: "Slider", score: 120, is_winner: true },
            team_b: { team_id: 2, team_name: "Maverick 2015", owner_id: 2, owner_name: "Maverick", score: 110, is_winner: false },
          },
        ],
      },
      {
        round_num: 3,
        round_label: "Finals",
        bye_teams: [],
        games: [
          {
            matchup_id: 30,
            is_playoff: true,
            is_consolation: false,
            game_label: "Championship",
            winner_team_id: 1,
            team_a: { team_id: 1, team_name: "Slider 2015", owner_id: 1, owner_name: "Slider", score: 140, is_winner: true },
            team_b: { team_id: 4, team_name: "Iceman 2015", owner_id: 4, owner_name: "Iceman", score: 100, is_winner: false },
          },
        ],
      },
    ],
  },
  consolation_bracket: {
    size: 6,
    bye_teams: [],
    rounds: [
      {
        round_num: 1,
        round_label: "First Round",
        bye_teams: [],
        games: [
          {
            matchup_id: 12,
            is_playoff: true,
            is_consolation: true,
            game_label: null,
            winner_team_id: 5,
            team_a: { team_id: 5, team_name: "Viper 2015", owner_id: 5, owner_name: "Viper", score: 90, is_winner: true },
            team_b: { team_id: 6, team_name: "Rooster 2015", owner_id: 6, owner_name: "Rooster", score: 50, is_winner: false },
          },
        ],
      },
    ],
  },
};

const POWER = {
  season_id: 1,
  season_year: 2015,
  through_week: 13,
  regular_season_weeks: 13,
  weights: { points_for_per_game: 0.4, all_play_win_pct: 0.25, win_pct: 0.2, recent_points_for_per_game: 0.15 },
  explainer: "Power score blends four within-season z-scores per the documented weights.",
  rows: [
    {
      rank: 1, team_id: 1, team_name: "Slider 2015", owner_id: 1, owner_name: "Slider",
      wins: 11, losses: 2, ties: 0, points_for: 1500, power_score: 1.42,
      points_for_per_game: 115, all_play_win_pct: 0.82, win_pct: 0.846, recent_points_for_per_game: 120,
      z_points_for: 1.3, z_all_play_win_pct: 1.2, z_win_pct: 1.1, z_recent: 1.0,
      standings_rank: 1, rank_delta: 0,
    },
  ],
};

let bracketResponse: unknown = BRACKET;

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}/bracket") return envelope(bracketResponse);
  if (path === "/v1/seasons/{season_id}/power") return envelope(POWER);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/playoffs"]}>
        <PlayoffsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  bracketResponse = BRACKET;
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("PlayoffsPage", () => {
  it("renders playoff and consolation brackets with round labels", async () => {
    renderPage();
    expect(await screen.findByText("Playoffs")).toBeInTheDocument();
    expect(await screen.findByText(/Post-regular-season matchups/i)).toBeInTheDocument();
    expect(screen.getByText("Championship Bracket")).toBeInTheDocument();
    expect(screen.getByText("Consolation Bracket")).toBeInTheDocument();
    expect(screen.getAllByText("First Round").length).toBeGreaterThan(0);
    expect(screen.getByText("Championship")).toBeInTheDocument();
    expect(screen.getAllByText("Slider").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/bye/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link").some((a) => a.getAttribute("href") === "/matchups/30")).toBe(true);
  });

  it("renders a DataGap when no bracket rows are available", async () => {
    bracketResponse = {
      ...BRACKET,
      available: false,
      reason: "bracket_unavailable",
      playoff_bracket: null,
      consolation_bracket: null,
    };

    renderPage();
    expect(await screen.findByText(/Bracket data isn't available/i)).toBeInTheDocument();
    expect(screen.queryByText("Championship Bracket")).not.toBeInTheDocument();
  });

  it("surfaces the 'Power at playoff entry' snapshot linking to the week-by-week lens", async () => {
    renderPage();
    expect(await screen.findByText("Power at playoff entry")).toBeInTheDocument();
    const lensLink = screen.getByText(/week-by-week lens/i).closest("a");
    expect(lensLink).toHaveAttribute("href", "/standings?lens=power");
  });
});
