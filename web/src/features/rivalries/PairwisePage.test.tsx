import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { PairwisePage } from "./PairwisePage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const AVAILABLE = {
  owner_a: { owner_id: 1, display_name: "Alpha" },
  owner_b: { owner_id: 2, display_name: "Bravo" },
  available: true,
  games_played: 3,
  a_wins: 2,
  b_wins: 1,
  ties: 0,
  a_win_pct: 0.6667,
  avg_margin_for_a: 12.5,
  playoff_meetings: 1,
  highest_scoring_meeting: { season_year: 2016, week: 1, matchup_id: 42, a_score: 150, b_score: 80 },
  most_lopsided_meeting: { season_year: 2016, week: 1, matchup_id: 42, margin_for_a: 70 },
};

function renderAt(payload: unknown) {
  mockGet.mockReset();
  mockGet.mockResolvedValue({ data: { data: payload, meta: {} } });
  return renderWithProviders(
    <Routes>
      <Route path="/rivalries/:a/vs/:b" element={<PairwisePage />} />
    </Routes>,
    ["/rivalries/1/vs/2"],
  );
}

beforeEach(() => mockGet.mockReset());

describe("PairwisePage", () => {
  it("renders the all-time record and deep-links a meeting to its box score", async () => {
    renderAt(AVAILABLE);
    expect(await screen.findByText("Alpha wins")).toBeInTheDocument();
    // Both managers' win counts surface (one in the stat grid).
    expect(screen.getByText("Most lopsided meeting")).toBeInTheDocument();
    const links = screen.getAllByRole("link");
    expect(links.some((a) => a.getAttribute("href") === "/matchups/42")).toBe(true);
  });

  it("shows an honest gap when two managers never met", async () => {
    renderAt({
      owner_a: { owner_id: 3, display_name: "Slider" },
      owner_b: { owner_id: 5, display_name: "Viper" },
      available: false,
      reason: "no_meetings",
      games_played: 0,
    });
    expect(await screen.findByText(/never met/i)).toBeInTheDocument();
    expect(screen.getByText(/Slider and Viper have no recorded games/i)).toBeInTheDocument();
  });
});
