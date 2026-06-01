import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { RecordsPage } from "./RecordsPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const RECORDS = {
  scored_era: [2016, 2017],
  highest_team_score: {
    available: true,
    value: 160.4,
    matchup_id: 7,
    owner_name: "Maverick",
    season_year: 2017,
    week: 1,
  },
  most_championships: { available: true, value: 2, owner_id: 1, owner_name: "Maverick" },
  best_player_week: {
    available: true,
    value: 35.5,
    player_id: 99,
    player_name: "Lamar Jackson",
    season_year: 2017,
    week: 2,
  },
  closest_rivalry: {
    available: true,
    games_played: 3,
    owner_a: { owner_id: 1, display_name: "Maverick" },
    owner_b: { owner_id: 2, display_name: "Iceman" },
  },
};

const CHAMPIONSHIPS = {
  seasons: [
    { season_year: 2016, champion: { team_id: 1, owner_id: 1, owner_name: "Maverick" } },
    { season_year: 2017, champion: { team_id: 2, owner_id: 1, owner_name: "Maverick" } },
  ],
};

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockImplementation(async (path: string) => {
    if (path === "/v1/records/championships") return { data: { data: CHAMPIONSHIPS, meta: {} } };
    return { data: { data: RECORDS, meta: {} } };
  });
});

function PairwiseProbe() {
  const { a, b } = useParams();
  return <div data-testid="pairwise">{`${a} vs ${b}`}</div>;
}

describe("RecordsPage", () => {
  it("deep-links each record to its canonical source", async () => {
    renderWithProviders(<RecordsPage />, ["/records"]);
    const highest = await screen.findByRole("link", { name: /Highest team score/i });
    expect(highest).toHaveAttribute("href", "/matchups/7");
    expect(screen.getByRole("link", { name: /Best player week/i })).toHaveAttribute(
      "href",
      "/players/99",
    );
    expect(screen.getByRole("link", { name: /Most championships/i })).toHaveAttribute(
      "href",
      "/managers/1",
    );
  });

  it("renders the championship dynasty timeline", async () => {
    renderWithProviders(<RecordsPage />, ["/records"]);
    expect(await screen.findByText("Championship History")).toBeInTheDocument();
    const champLinks = await screen.findAllByText("Maverick");
    expect(champLinks.length).toBeGreaterThan(0);
  });

  it("flows from a record to its source page (closest rivalry → pairwise)", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/records" element={<RecordsPage />} />
        <Route path="/rivalries/:a/vs/:b" element={<PairwiseProbe />} />
      </Routes>,
      ["/records"],
    );
    const rivalry = await screen.findByRole("link", { name: /Closest rivalry/i });
    expect(rivalry).toHaveAttribute("href", "/rivalries/1/vs/2");
    await userEvent.click(rivalry);
    await waitFor(() => expect(screen.getByTestId("pairwise")).toHaveTextContent("1 vs 2"));
  });
});
