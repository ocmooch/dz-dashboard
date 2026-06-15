import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
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
    { player_id: 3, player_name: "Bye Guy", position: "WR", nfl_team: "DET", roster_slot: "BN", is_starter: false, league_points: 0, zero_reason: "bye", zero_detail: null, acquisition_type: "draft", acquisition_week: 1 },
    { player_id: 4, player_name: "Scratch Guy", position: "WR", nfl_team: "SEA", roster_slot: "BN", is_starter: false, league_points: 0, zero_reason: "did_not_play", zero_detail: null, acquisition_type: "draft", acquisition_week: 1 },
    { player_id: 5, player_name: "Mismatch Guy", position: "WR", nfl_team: "KC", roster_slot: "BN", is_starter: false, league_points: 0, zero_reason: "unexpected", zero_detail: "nflverse credits 8 pts but the league scored 0.", acquisition_type: "draft", acquisition_week: 1 },
    { player_id: 6, player_name: "Goose Egg", position: "WR", nfl_team: "CHI", roster_slot: "BN", is_starter: false, league_points: 0, zero_reason: null, zero_detail: null, acquisition_type: "draft", acquisition_week: 1 },
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

const TRANSACTIONS = {
  team_id: 10,
  season_year: 2017,
  transactions: [
    {
      transaction_id: 1,
      transaction_type: "waiver_add",
      executed_at: "2017-09-12T10:15:00+00:00",
      effective_week: 2,
      player_id: 3,
      player_name: "Waiver Wendell",
      direction: "in",
      waiver_priority_used: 4,
      faab_bid: null,
      counterpart_team_id: null,
      counterpart_team_name: null,
      notes: "Iceman",
      extra_data: null,
    },
    {
      transaction_id: 2,
      transaction_type: "lineup_change",
      executed_at: "2017-09-17T09:05:00+00:00",
      effective_week: 2,
      player_id: 1,
      player_name: "Kept Player",
      direction: null,
      waiver_priority_used: null,
      faab_bid: null,
      counterpart_team_id: null,
      counterpart_team_name: null,
      notes: "Iceman",
      extra_data: { from_slot: "BN", to_slot: "WR" },
    },
  ],
};

const ROSTER_MOVES = {
  team_id: 10,
  season_year: 2017,
  is_scored: true,
  available: true,
  roster_weeks: [1, 2],
  moves: [
    { week: 1, player_id: 1, player_name: "Kept Player", position: "RB", action: "retain" },
    { week: 2, player_id: 3, player_name: "Waiver Wendell", position: "RB", action: "add" },
    { week: 2, player_id: 2, player_name: "Dropped D/ST", position: "DEF", action: "drop" },
  ],
};

const OWNER_SEASONS = {
  owner_id: 5,
  display_name: "Iceman",
  seasons: [
    { season_id: 1, season_year: 2017, team_id: 10, team_name: "Iceman 2017", wins: 2, losses: 0, ties: 0, points_for: 235, final_rank: 1, made_playoffs: true, is_champion: false },
    { season_id: 2, season_year: 2016, team_id: 9, team_name: "Iceman 2016", wins: 7, losses: 7, ties: 0, points_for: 1400, final_rank: 5, made_playoffs: null, is_champion: false },
  ],
};

let rosterMoves: unknown = ROSTER_MOVES;

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="loc">{location.pathname}</div>;
}

function routeByPath(path: string) {
  if (path === "/v1/teams/{team_id}") return envelope(OVERVIEW);
  if (path === "/v1/teams/{team_id}/roster") return envelope(ROSTER);
  if (path === "/v1/teams/{team_id}/schedule") return envelope(SCHEDULE);
  if (path === "/v1/teams/{team_id}/scoring-trend") return envelope(TREND);
  if (path === "/v1/teams/{team_id}/transactions") return envelope(TRANSACTIONS);
  if (path === "/v1/teams/{team_id}/roster-moves") return envelope(rosterMoves);
  if (path === "/v1/owners/{owner_id}/seasons") return envelope(OWNER_SEASONS);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/teams/10"]}>
        <Routes>
          <Route path="/teams/:teamId" element={<TeamPage />} />
          <Route path="/matchups" element={<div>Matchups route</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  rosterMoves = ROSTER_MOVES;
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

  it("explains roster zeroes with the same labels as box scores", async () => {
    renderPage();
    await screen.findByText("Ice QB One");

    const pointsCell = (name: string) => screen.getByText(name).closest("tr")!.querySelector(".dz-num:last-child")!;
    expect(pointsCell("Bye Guy")).toHaveTextContent("Bye");
    expect(pointsCell("Scratch Guy")).toHaveTextContent("Out");
    expect(pointsCell("Mismatch Guy")).toHaveTextContent("0.00!");
    expect(pointsCell("Goose Egg")).toHaveTextContent("0.00");
    expect(pointsCell("Goose Egg")).not.toHaveTextContent(/Bye|Out|!/);
    expect(pointsCell("Ice D/ST")).toHaveTextContent(/No scored data/i);
  });

  it("renders the schedule with a box-score deep link", async () => {
    renderPage();
    await screen.findByText(/vs Goose/i);
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/matchups/100");
    expect(link).toBeDefined();
  });

  it("uses weekly matchups for schedule links when box scores are unavailable", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/v1/teams/{team_id}") return Promise.resolve(envelope({ ...OVERVIEW, is_scored: false }));
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    await screen.findByText(/vs Goose/i);
    const link = screen.getAllByRole("link").find((a) => a.getAttribute("href") === "/matchups?week=1");
    expect(link).toBeDefined();
  });

  it("navigates to the selected owner's team season", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Iceman 2017" });
    await userEvent.selectOptions(await screen.findByLabelText("Team season"), "9");
    await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/teams/9"));
  });

  it("renders the scoring-trend chart vs league average", async () => {
    renderPage();
    expect(
      await screen.findByLabelText(/Team score vs league average by week/i),
    ).toBeInTheDocument();
  });

  it("renders exact recorded transactions with dates and waiver details", async () => {
    renderPage();
    expect(await screen.findByText("Transactions")).toBeInTheDocument();
    expect((await screen.findAllByText("Waiver Wendell")).length).toBeGreaterThan(0);
    expect(screen.getByText("waiver add")).toBeInTheDocument();
    expect(screen.getByText(/waiver priority 4/i)).toBeInTheDocument();
    expect(screen.getByText(/BN to WR/i)).toBeInTheDocument();
  });

  it("renders in-season add/drop rows with action pills and a retained count", async () => {
    renderPage();
    await screen.findByText("Waiver Wendell");
    expect(screen.getByText("Dropped D/ST")).toBeInTheDocument();
    expect(screen.getByText("add")).toBeInTheDocument();
    expect(screen.getByText("drop")).toBeInTheDocument();
    // Retained roster-diff players are a de-emphasised secondary count, not full rows.
    expect(screen.getByText(/1 player retained all season/i)).toBeInTheDocument();
    expect(screen.getAllByText("Kept Player")).toHaveLength(1);
  });

  it("renders the roster-history gap (not zeros) when moves are unavailable", async () => {
    rosterMoves = {
      team_id: 10,
      season_year: 2017,
      is_scored: true,
      available: false,
      roster_weeks: [],
      moves: [],
    };
    renderPage();
    const gap = await screen.findByText(/Week-by-week roster history isn't available/i);
    expect(gap).toBeInTheDocument();
    expect(gap.textContent).not.toMatch(/\b0\b/);
  });

  it("shows no roster churn when there is retain-only history", async () => {
    rosterMoves = {
      team_id: 10,
      season_year: 2017,
      is_scored: true,
      available: true,
      roster_weeks: [1, 2],
      moves: [{ week: 1, player_id: 1, player_name: "Kept Player", position: "RB", action: "retain" }],
    };
    renderPage();
    expect(await screen.findByText(/No roster churn detected/i)).toBeInTheDocument();
  });
});
