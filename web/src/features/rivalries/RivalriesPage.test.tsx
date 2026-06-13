import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { RivalriesPage } from "./RivalriesPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const MATRIX = {
  owners: [
    { owner_id: 1, display_name: "Alpha", is_active: true },
    { owner_id: 2, display_name: "Bravo", is_active: true },
    { owner_id: 3, display_name: "Charlie", is_active: false },
  ],
  cells: [
    { a: 1, b: 1, games: 0, a_win_pct: null },
    { a: 1, b: 2, games: 3, a_win_pct: 0.67 },
    { a: 1, b: 3, games: 2, a_win_pct: 0.5 },
    { a: 2, b: 1, games: 3, a_win_pct: 0.33 },
    { a: 2, b: 2, games: 0, a_win_pct: null },
    { a: 2, b: 3, games: 0, a_win_pct: null },
    { a: 3, b: 1, games: 2, a_win_pct: 0.5 },
    { a: 3, b: 2, games: 0, a_win_pct: null },
    { a: 3, b: 3, games: 0, a_win_pct: null },
  ],
};

const INSIGHTS = {
  records: {
    available: true,
    closest_game: {
      winner: { owner_id: 1, display_name: "Alpha" },
      loser: { owner_id: 2, display_name: "Bravo" },
      winner_score: 103.7,
      loser_score: 103.7,
      margin: 0.04,
      combined: 207.4,
      season_year: 2023,
      week: 11,
      matchup_id: 9001,
    },
  },
  streaks: {
    available: true,
    longest: {
      owner: { owner_id: 1, display_name: "Alpha" },
      opponent: { owner_id: 3, display_name: "Charlie" },
      length: 9,
      from_year: 2016,
      to_year: 2020,
      last_matchup_id: 9100,
    },
    active: [],
  },
  intensity: {
    available: true,
    leaderboard: [
      {
        owner_a: { owner_id: 1, display_name: "Alpha" },
        owner_b: { owner_id: 2, display_name: "Bravo" },
        heat: 81.2,
        games: 27,
        a_wins: 14,
        b_wins: 13,
        ties: 0,
        playoff_meetings: 2,
        last_meeting: { season_year: 2024, week: 3, matchup_id: 9200 },
      },
    ],
  },
  nemeses: {
    available: true,
    managers: [
      {
        owner: { owner_id: 1, display_name: "Alpha" },
        nemesis: { opponent: { owner_id: 2, display_name: "Bravo" }, games: 27, wins: 9, losses: 18, ties: 0, win_pct: 0.333 },
        favorite_victim: null,
      },
    ],
  },
  playoffs: { available: false, reason: "no_playoff_meetings" },
};

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockImplementation((path: string) =>
    Promise.resolve({
      data: { data: path.includes("/rivalries/insights") ? INSIGHTS : MATRIX, meta: {} },
    }),
  );
});

describe("RivalriesPage", () => {
  it("renders the rivalry matrix with win-pct heat cells", async () => {
    renderWithProviders(<RivalriesPage />, ["/rivalries"]);
    expect(await screen.findByRole("gridcell", { name: "Alpha vs Bravo: 67%" })).toBeInTheDocument();
    expect(screen.getByRole("gridcell", { name: "Bravo vs Alpha: 33%" })).toBeInTheDocument();
  });

  it("hides inactive managers until the toggle is checked", async () => {
    renderWithProviders(<RivalriesPage />, ["/rivalries"]);
    // Charlie is inactive: absent by default, present once toggled in.
    expect(await screen.findByRole("rowheader", { name: "Alpha" })).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: "Charlie" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /inactive managers/i }));
    expect(await screen.findByRole("rowheader", { name: "Charlie" })).toBeInTheDocument();
  });

  it("navigates to the pairwise page when a cell is clicked", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/rivalries" element={<RivalriesPage />} />
        <Route path="/rivalries/:a/vs/:b" element={<PairwiseProbe />} />
      </Routes>,
      ["/rivalries"],
    );
    const cell = await screen.findByRole("gridcell", { name: "Alpha vs Bravo: 67%" });
    await userEvent.click(cell);
    await waitFor(() => expect(screen.getByTestId("pairwise")).toHaveTextContent("1 vs 2"));
  });

  it("renders the insight bands below the matrix", async () => {
    renderWithProviders(<RivalriesPage />, ["/rivalries"]);
    // Centerpiece leaderboard + a superlative + a streak all hydrate from the bundle.
    expect(await screen.findByText("Hottest Rivalries")).toBeInTheDocument();
    expect(screen.getByText("Closest game ever")).toBeInTheDocument();
    expect(screen.getByText(/Alpha over Charlie/)).toBeInTheDocument();
    // The empty playoff band shows the honest affordance, not a fabricated row.
    expect(screen.getByText(/No postseason meetings on record/)).toBeInTheDocument();
  });
});

function PairwiseProbe() {
  const { a, b } = useParams();
  return <div data-testid="pairwise">{`${a} vs ${b}`}</div>;
}
