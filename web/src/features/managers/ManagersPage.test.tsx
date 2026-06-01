import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { ManagersPage } from "./ManagersPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const blank = { trophy_case: [] as never[] };
const OWNERS = [
  // Alpha: most titles + best win%.  Bravo: most points + most seasons.
  { owner_id: 1, display_name: "Alpha", seasons_played: 5, total_wins: 40, total_losses: 20, total_ties: 0, total_points_for: 6000, championships: 2, best_finish: 1, avg_finish: 3.2, ...blank },
  { owner_id: 2, display_name: "Bravo", seasons_played: 8, total_wins: 50, total_losses: 50, total_ties: 0, total_points_for: 7000, championships: 0, best_finish: 4, avg_finish: 6.1, ...blank },
];

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockResolvedValue({ data: { data: { owners: OWNERS }, meta: {} } });
});

describe("ManagersPage", () => {
  it("renders the league legends and a career row per manager", async () => {
    renderWithProviders(<ManagersPage />, ["/managers"]);

    // Legends are owner-centric superlatives computed from the list.
    const titles = (await screen.findByText("Most titles")).closest("section")!;
    expect(within(titles).getByText("Alpha")).toBeInTheDocument();
    const points = screen.getByText("Most points").closest("section")!;
    expect(within(points).getByText("Bravo")).toBeInTheDocument();

    // Both managers appear in the table, linking to their profiles.
    const link = screen.getByRole("link", { name: /Alpha/ });
    expect(link).toHaveAttribute("href", "/managers/1");
  });

  it("re-sorts the table when a sortable column header is clicked", async () => {
    renderWithProviders(<ManagersPage />, ["/managers"]);
    await screen.findByText("Every Manager");

    const order = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getByRole("link").textContent);
    // Default order is the BFF order (titles): Alpha first.
    expect(order()[0]).toContain("Alpha");

    await userEvent.click(screen.getByRole("button", { name: /Points For/ }));
    // By points-for, Bravo (7000) leads Alpha (6000).
    expect(order()[0]).toContain("Bravo");
  });

  it("shows an error state when the request fails", async () => {
    mockGet.mockResolvedValue({ error: { detail: "boom" } });
    renderWithProviders(<ManagersPage />, ["/managers"]);
    expect(await screen.findByText(/Signal lost/i)).toBeInTheDocument();
  });
});
