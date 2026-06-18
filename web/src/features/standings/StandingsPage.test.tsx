import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StandingsPage } from "./StandingsPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

let currentSeason = { season_id: 2, season_year: 2020, is_scored: true };

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: currentSeason,
    seasons: [currentSeason],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const STANDINGS = {
  season_id: 2,
  season_year: 2016,
  through_week: 14,
  regular_season_weeks: 14,
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

const powerRow = (rank: number, owner: string, power: number, delta: number, standingsRank: number) => ({
  rank,
  team_id: rank === 1 ? 10 : 11,
  team_name: `${owner} 2016`,
  owner_id: rank,
  owner_name: owner,
  wins: 11,
  losses: 3,
  ties: 0,
  points_for: 1600,
  power_score: power,
  points_for_per_game: 114.3,
  all_play_win_pct: 0.78,
  win_pct: 0.786,
  recent_points_for_per_game: 120,
  z_points_for: 1.2,
  z_all_play_win_pct: 1.0,
  z_win_pct: 1.0,
  z_recent: 1.1,
  standings_rank: standingsRank,
  rank_delta: delta,
});

const POWER = {
  season_id: 2,
  season_year: 2016,
  through_week: 14,
  regular_season_weeks: 14,
  weights: { points_for_per_game: 0.4, all_play_win_pct: 0.25, win_pct: 0.2, recent_points_for_per_game: 0.15 },
  explainer: "Power score blends four within-season z-scores per the documented weights.",
  rows: [powerRow(1, "Iceman", 1.54, 1, 2), powerRow(2, "Goose", -0.32, -1, 1)],
};

const POWER_TIMELINE = {
  season_id: 2,
  season_year: 2016,
  regular_season_weeks: 14,
  teams: [
    { team_id: 10, team_name: "Iceman 2016", owner_name: "Iceman", points: [
      { week: 1, rank: 2, power_score: 0.4 },
      { week: 2, rank: 1, power_score: 1.54 },
    ] },
    { team_id: 11, team_name: "Goose 2016", owner_name: "Goose", points: [
      { week: 1, rank: 1, power_score: 0.8 },
      { week: 2, rank: 2, power_score: -0.32 },
    ] },
  ],
};

let insightsResponse: unknown = INSIGHTS;
let conferencesResponse: unknown = { available: false, reason: "no_conferences_this_season", conferences: [] };
let conferencesError = false;
let regularSeasonWeeks = 14;

const DIVISION_TEAM = {
  ...STANDINGS.rows[0],
  overall_rank: 1,
  conference_rank: 1,
  division_wins: 6,
  division_losses: 1,
  division_ties: 0,
};

const CONFERENCES = {
  season_id: 2,
  season_year: 2018,
  through_week: 14,
  regular_season_weeks: 14,
  available: true,
  reason: null,
  mapping_issues: [],
  conferences: [
    { conference_id: 20181, division_number: 1, name: "Westeros", teams: [DIVISION_TEAM] },
    {
      conference_id: 20182,
      division_number: 2,
      name: "Essos",
      teams: [{ ...DIVISION_TEAM, ...STANDINGS.rows[1], overall_rank: 2, conference_rank: 1, division_wins: 4, division_losses: 3 }],
    },
  ],
};

function routeByPath(path: string, options?: { params?: { query?: { through_week?: number } } }) {
  const throughWeek = options?.params?.query?.through_week;
  if (path === "/v1/seasons/{season_id}/standings") {
    return envelope({
      ...STANDINGS,
      through_week: throughWeek ? Math.min(throughWeek, regularSeasonWeeks) : regularSeasonWeeks,
      regular_season_weeks: regularSeasonWeeks,
      rank_basis: throughWeek ? "computed" : STANDINGS.rank_basis,
    });
  }
  if (path === "/v1/seasons/{season_id}/standings/timeline") return envelope(TIMELINE);
  if (path === "/v1/seasons/{season_id}/standings/insights") return envelope(insightsResponse);
  if (path === "/v1/seasons/{season_id}/conferences") {
    if (conferencesError) return { data: undefined, error: { detail: "offline" } };
    return envelope(
      throughWeek && typeof conferencesResponse === "object" && conferencesResponse
        ? {
            ...conferencesResponse,
            through_week: Math.min(throughWeek, regularSeasonWeeks),
            regular_season_weeks: regularSeasonWeeks,
          }
        : conferencesResponse,
    );
  }
  if (path === "/v1/seasons/{season_id}/power") return envelope(POWER);
  if (path === "/v1/seasons/{season_id}/power/timeline") return envelope(POWER_TIMELINE);
  throw new Error(`unexpected path ${path}`);
}

function renderPage(initialPath = "/standings") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <StandingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  currentSeason = { season_id: 2, season_year: 2020, is_scored: true };
  insightsResponse = INSIGHTS;
  conferencesResponse = { available: false, reason: "no_conferences_this_season", conferences: [] };
  conferencesError = false;
  regularSeasonWeeks = 14;
  get.mockReset();
  get.mockImplementation((path: string, options?: { params?: { query?: { through_week?: number } } }) =>
    Promise.resolve(routeByPath(path, options)),
  );
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

  it("?lens=power swaps to the power table with scores and the model-vs-record movement", async () => {
    renderPage("/standings?lens=power");
    expect((await screen.findAllByText("Iceman")).length).toBeGreaterThan(0);
    expect(screen.getByText("1.54")).toBeInTheDocument();
    expect(screen.getByText("-0.32")).toBeInTheDocument();
    expect(screen.getByText(/▲ 1/)).toBeInTheDocument();
    expect(screen.getByText(/▼ 1/)).toBeInTheDocument();
  });

  it("power lens offers a week selector and the power-over-time chart", async () => {
    renderPage("/standings?lens=power");
    expect(await screen.findByLabelText("Power ranking by week (rank 1 on top)")).toBeInTheDocument();
    expect(screen.getByLabelText("Select week")).toBeInTheDocument();
  });

  it("record lens (default) does not fetch power", async () => {
    renderPage();
    await screen.findByText("Champion");
    const paths = get.mock.calls.map((c) => c[0]);
    expect(paths).not.toContain("/v1/seasons/{season_id}/power");
  });

  it("renders historical divisions as stacked full-width tables with DIV and OVR", async () => {
    currentSeason = { season_id: 2, season_year: 2018, is_scored: true };
    conferencesResponse = CONFERENCES;
    renderPage();
    expect(await screen.findByRole("heading", { name: "Westeros" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Essos" })).toBeInTheDocument();
    expect(screen.getAllByText("OVR")).toHaveLength(2);
    expect(screen.getAllByText("DIV")).toHaveLength(2);
    expect(screen.queryByText("Conference Standings")).not.toBeInTheDocument();
  });

  it("renders 2010 as three source-ordered divisions", async () => {
    currentSeason = { season_id: 2, season_year: 2010, is_scored: true };
    conferencesResponse = {
      ...CONFERENCES,
      season_year: 2010,
      conferences: [1, 2, 3].map((division) => ({
        conference_id: 20100 + division,
        division_number: division,
        name: null,
        teams: [{ ...DIVISION_TEAM, team_id: 10 + division, conference_rank: 1 }],
      })),
    };
    renderPage();
    expect(await screen.findByRole("heading", { name: "Division 1" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Division 2" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Division 3" })).toBeInTheDocument();
  });

  it("sends one Record week to standings, insights, and divisions and hides Finish", async () => {
    currentSeason = { season_id: 2, season_year: 2018, is_scored: true };
    conferencesResponse = CONFERENCES;
    renderPage();
    const select = await screen.findByLabelText("Select week");
    fireEvent.change(select, { target: { value: "7" } });
    await waitFor(() => {
      const weeklyCalls = get.mock.calls.filter((call) =>
        [
          "/v1/seasons/{season_id}/standings",
          "/v1/seasons/{season_id}/standings/insights",
          "/v1/seasons/{season_id}/conferences",
        ].includes(call[0]),
      );
      expect(weeklyCalls.some((call) => call[1]?.params?.query?.through_week === 7)).toBe(true);
    });
    expect(screen.queryByText("Finish")).not.toBeInTheDocument();
  });

  it("keeps the modern season on one overall table", async () => {
    renderPage();
    expect(await screen.findByText("Champion")).toBeInTheDocument();
    expect(screen.getAllByRole("table")).toHaveLength(2); // standings + Robbed & Blessed
    expect(screen.queryByRole("heading", { name: "Westeros" })).not.toBeInTheDocument();
  });

  it("shows an error when historical division loading fails", async () => {
    currentSeason = { season_id: 2, season_year: 2018, is_scored: true };
    conferencesError = true;
    renderPage();
    expect(await screen.findByText("Could not reach the analytics service.")).toBeInTheDocument();
    const beforeRetry = get.mock.calls.filter(
      (call) => call[0] === "/v1/seasons/{season_id}/conferences",
    ).length;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      const afterRetry = get.mock.calls.filter(
        (call) => call[0] === "/v1/seasons/{season_id}/conferences",
      ).length;
      expect(afterRetry).toBeGreaterThan(beforeRetry);
    });
  });

  it("clamps a stale URL week when switching to a shorter season", async () => {
    currentSeason = { season_id: 2, season_year: 2011, is_scored: true };
    regularSeasonWeeks = 13;
    conferencesResponse = { ...CONFERENCES, season_year: 2011, regular_season_weeks: 13 };
    renderPage("/standings?week=14");
    await screen.findByLabelText("Select week");
    await waitFor(() => expect(screen.getByLabelText("Select week")).toHaveValue("13"));
    await waitFor(() => {
      expect(
        get.mock.calls.some(
          (call) =>
            call[0] === "/v1/seasons/{season_id}/conferences" &&
            call[1]?.params?.query?.through_week === 13,
        ),
      ).toBe(true);
    });
  });
});
