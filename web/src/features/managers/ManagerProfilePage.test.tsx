import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { ManagerProfilePage } from "./ManagerProfilePage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const CAREER = {
  owner_id: 1,
  display_name: "Alpha",
  seasons_played: 3,
  total_wins: 30,
  total_losses: 12,
  total_ties: 0,
  total_points_for: 4200,
  championships: 1,
  best_finish: 1,
  avg_finish: 2.5,
  trophy_case: [{ season_year: 2020, team_name: "Alpha FC", finish: 1, is_champion: true }],
};

const SEASONS = [
  // record-only season: 0 PF -> must render an honest gap, not "0".
  { season_id: 10, season_year: 2014, team_id: 100, team_name: "Old Alpha", wins: 8, losses: 6, ties: 0, points_for: 0, final_rank: 5, made_playoffs: false, is_champion: false },
  // scored, championship season.
  { season_id: 11, season_year: 2020, team_id: 101, team_name: "Alpha FC", wins: 12, losses: 2, ties: 0, points_for: 1800.5, final_rank: 1, made_playoffs: true, is_champion: true },
];

const TRAJ = [
  { season_year: 2014, final_rank: 5, points_for: 0 },
  { season_year: 2020, final_rank: 1, points_for: 1800.5 },
];

const MATRIX = {
  owners: [
    { owner_id: 1, display_name: "Alpha" },
    { owner_id: 2, display_name: "Bravo" },
  ],
  cells: [
    { a: 1, b: 2, games: 4, a_win_pct: 0.75 },
    { a: 2, b: 1, games: 4, a_win_pct: 0.25 },
  ],
};

function mockEndpoints() {
  mockGet.mockImplementation((path: string) => {
    if (path === "/v1/owners/{owner_id}") return Promise.resolve({ data: { data: CAREER, meta: {} } });
    if (path === "/v1/owners/{owner_id}/seasons")
      return Promise.resolve({ data: { data: { owner_id: 1, display_name: "Alpha", seasons: SEASONS }, meta: {} } });
    if (path === "/v1/owners/{owner_id}/trajectory")
      return Promise.resolve({ data: { data: { owner_id: 1, display_name: "Alpha", points: TRAJ }, meta: {} } });
    if (path === "/v1/owners/rivalry-matrix") return Promise.resolve({ data: { data: MATRIX, meta: {} } });
    return Promise.resolve({ error: { detail: "unexpected" } });
  });
}

function renderProfile(id = "1") {
  return renderWithProviders(
    <Routes>
      <Route path="/managers/:ownerId" element={<ManagerProfilePage />} />
    </Routes>,
    [`/managers/${id}`],
  );
}

beforeEach(() => mockGet.mockReset());

describe("ManagerProfilePage", () => {
  it("renders the career header, trophy case, and season table", async () => {
    mockEndpoints();
    renderProfile();

    expect(await screen.findByRole("heading", { name: "Alpha" })).toBeInTheDocument();
    // Trophy case section.
    expect(screen.getByText("Hardware")).toBeInTheDocument();
    // Season table has both seasons, scored PF rendered as a number.
    expect(screen.getByText("1,800.50")).toBeInTheDocument();
  });

  it("shows an honest gap for a record-only (unscored) season instead of a 0", async () => {
    mockEndpoints();
    renderProfile();

    const oldRow = (await screen.findByText("Old Alpha")).closest("tr")!;
    expect(within(oldRow).getByText(/scoring not available for this season/i)).toBeInTheDocument();
    expect(within(oldRow).queryByText("0")).not.toBeInTheDocument();
  });

  it("links rivalry snapshot rows to the pairwise page", async () => {
    mockEndpoints();
    renderProfile();

    const rival = await screen.findByRole("link", { name: /Bravo/ });
    expect(rival).toHaveAttribute("href", "/rivalries/1/vs/2");
  });

  it("renders a not-found state when the owner does not exist", async () => {
    mockGet.mockResolvedValue({ error: { detail: "No owner with id 999" } });
    renderProfile("999");
    expect(await screen.findByText("Manager not found")).toBeInTheDocument();
  });
});
