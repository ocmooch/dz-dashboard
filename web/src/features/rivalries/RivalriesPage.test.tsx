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
    { owner_id: 1, display_name: "Alpha" },
    { owner_id: 2, display_name: "Bravo" },
  ],
  cells: [
    { a: 1, b: 1, games: 0, a_win_pct: null },
    { a: 1, b: 2, games: 3, a_win_pct: 0.67 },
    { a: 2, b: 1, games: 3, a_win_pct: 0.33 },
    { a: 2, b: 2, games: 0, a_win_pct: null },
  ],
};

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockResolvedValue({ data: { data: MATRIX, meta: {} } });
});

describe("RivalriesPage", () => {
  it("renders the rivalry matrix with win-pct heat cells", async () => {
    renderWithProviders(<RivalriesPage />, ["/rivalries"]);
    expect(await screen.findByRole("gridcell", { name: "Alpha vs Bravo: 67%" })).toBeInTheDocument();
    expect(screen.getByRole("gridcell", { name: "Bravo vs Alpha: 33%" })).toBeInTheDocument();
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
});

function PairwiseProbe() {
  const { a, b } = useParams();
  return <div data-testid="pairwise">{`${a} vs ${b}`}</div>;
}
