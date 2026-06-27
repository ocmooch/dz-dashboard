import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { VizLabPage } from "./VizLabPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const OWNERS = [
  { owner_id: 1, display_name: "Alpha", seasons_played: 12, total_wins: 0, total_losses: 0, total_ties: 0, total_points_for: 0, championships: 2, sackos: 1, is_active: true, qualified: true, trophy_case: [] },
  { owner_id: 2, display_name: "Bravo", seasons_played: 4, total_wins: 0, total_losses: 0, total_ties: 0, total_points_for: 0, championships: 0, sackos: 0, is_active: false, qualified: false, trophy_case: [] },
];

const SEASONS = [
  { season_id: 11, season_year: 2018, team_id: 100, team_name: "Alpha FC", wins: 3, losses: 11, ties: 0, points_for: 1200, final_rank: 12, made_playoffs: false, is_champion: false, is_sacko: true },
  { season_id: 12, season_year: 2020, team_id: 101, team_name: "Alpha FC", wins: 12, losses: 2, ties: 0, points_for: 1800, final_rank: 1, made_playoffs: true, is_champion: true, is_sacko: false },
];

const TEAMS = [
  { owner_id: 1, owner_name: "Alpha", season_year: 2018, points_for: 1200, is_champion: false },
  { owner_id: 1, owner_name: "Alpha", season_year: 2020, points_for: 1800, is_champion: true },
  { owner_id: 2, owner_name: "Bravo", season_year: 2018, points_for: 1100, is_champion: false },
  { owner_id: 2, owner_name: "Bravo", season_year: 2020, points_for: 1000, is_champion: false },
];

const SEASON_LIST = [{ season_id: 7, season_year: 2020, is_scored: true, status: "completed" }];
const WEEKLY = {
  season_id: 7,
  season_year: 2020,
  regular_season_weeks: 2,
  available: true,
  reason: null,
  teams: [
    {
      team_id: 1,
      team_name: "Alpha FC",
      owner_id: 1,
      owner_name: "Alpha",
      scores: [
        { week: 1, score: 100, is_playoff: false },
        { week: 2, score: 120, is_playoff: false },
      ],
    },
  ],
};
const EFFICIENCY = {
  season_id: 7,
  season_year: 2020,
  available: true,
  reason: null,
  teams: [
    { team_id: 1, owner_id: 1, owner_name: "Alpha", team_name: "Alpha FC", captured: 113, optimal: 126, efficiency_pct: 0.8968, points_for: 1400, weeks: 2 },
  ],
};

function mockEndpoints() {
  mockGet.mockImplementation((path: string) => {
    if (path === "/v1/owners") return Promise.resolve({ data: { data: { owners: OWNERS }, meta: {} } });
    if (path === "/v1/owners/{owner_id}/seasons")
      return Promise.resolve({ data: { data: { owner_id: 1, display_name: "Alpha", seasons: SEASONS }, meta: {} } });
    if (path === "/v1/teams") return Promise.resolve({ data: { data: { teams: TEAMS }, meta: {} } });
    if (path === "/v1/seasons") return Promise.resolve({ data: { data: { seasons: SEASON_LIST }, meta: {} } });
    if (path === "/v1/seasons/{season_id}/weekly-scores") return Promise.resolve({ data: { data: WEEKLY, meta: {} } });
    if (path === "/v1/seasons/{season_id}/efficiency") return Promise.resolve({ data: { data: EFFICIENCY, meta: {} } });
    return Promise.resolve({ error: { detail: "unexpected" } });
  });
}

beforeEach(() => mockGet.mockReset());

describe("VizLabPage", () => {
  it("renders the lab with the Legacy Spine exhibit defaulting to the longest-tenured manager", async () => {
    mockEndpoints();
    renderWithProviders(<VizLabPage />);

    expect(await screen.findByRole("heading", { name: "Viz Lab" })).toBeInTheDocument();
    expect(screen.getByText("Career Legacy Spine")).toBeInTheDocument();

    // The spine rendered (its accessible figure + data-table fallback are present),
    // and the manager picker defaults to Alpha (12 seasons, the richest spine).
    expect(await screen.findByText("Data table")).toBeInTheDocument();
    const picker = screen.getByLabelText("Manager") as HTMLSelectElement;
    expect(picker.value).toBe("1");
    // The Sacko marker survives in the fallback table.
    expect(screen.getByText("Sacko")).toBeInTheDocument();

    // The other exhibits render from their endpoints.
    expect(screen.getByText("Dynasty Stream")).toBeInTheDocument();
    expect(await screen.findByText("Weekly Scoring Beeswarm")).toBeInTheDocument();
    expect(screen.getByText("Manager Efficiency (Lineup IQ)")).toBeInTheDocument();
  });
});
