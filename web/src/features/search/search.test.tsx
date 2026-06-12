import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GlobalSearch } from "./GlobalSearch";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

const setSeasonId = vi.fn();
vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({ setSeasonId, current: null, seasons: [], isLoading: false }),
}));

const HITS = [
  { type: "owner", id: 7, label: "Maverick", sublabel: "Manager", href: "/managers/7" },
  { type: "player", id: 12, label: "Justin Jefferson", sublabel: "WR · MIN", href: "/players/12" },
  { type: "season", id: 3, label: "2016 season", sublabel: "Standings", href: "/standings" },
];

const envelope = (hits: unknown[]) => ({ data: { data: { query: "x", hits }, meta: {} }, error: undefined });

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="loc">{loc.pathname}</div>;
}

function renderSearch() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <GlobalSearch />
        <Routes>
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  setSeasonId.mockReset();
  get.mockResolvedValue(envelope(HITS));
});

afterEach(() => vi.clearAllMocks());

describe("GlobalSearch", () => {
  it("queries /v1/search after typing and renders ranked hits", async () => {
    renderSearch();
    await userEvent.type(screen.getByLabelText("Global search"), "ma");
    expect(await screen.findByText("Maverick")).toBeInTheDocument();
    expect(screen.getByText("Justin Jefferson")).toBeInTheDocument();
    const call = get.mock.calls.find((c) => c[0] === "/v1/search");
    expect(call).toBeDefined();
    expect((call![1] as any).params.query.q).toBe("ma");
  });

  it("navigates to a player's deep link when chosen by mouse", async () => {
    renderSearch();
    await userEvent.type(screen.getByLabelText("Global search"), "jeff");
    await userEvent.click(await screen.findByText("Justin Jefferson"));
    await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/players/12"));
  });

  it("switches the season context and routes to standings for a season hit", async () => {
    renderSearch();
    await userEvent.type(screen.getByLabelText("Global search"), "2016");
    await userEvent.click(await screen.findByText("2016 season"));
    expect(setSeasonId).toHaveBeenCalledWith(3);
    await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/standings"));
  });

  it("supports keyboard selection (ArrowDown + Enter)", async () => {
    renderSearch();
    const input = screen.getByLabelText("Global search");
    await userEvent.type(input, "ma");
    await screen.findByText("Maverick");
    await userEvent.keyboard("{ArrowDown}{Enter}");
    await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/players/12"));
  });

  it("shows an honest empty state when nothing matches", async () => {
    get.mockResolvedValue(envelope([]));
    renderSearch();
    await userEvent.type(screen.getByLabelText("Global search"), "zzz");
    expect(await screen.findByText(/No matches for/i)).toBeInTheDocument();
  });

  it("does not query for a blank input", async () => {
    renderSearch();
    const input = screen.getByLabelText("Global search");
    await userEvent.type(input, "  ");
    await waitFor(() => {
      expect(get.mock.calls.filter((c) => c[0] === "/v1/search")).toHaveLength(0);
    });
  });

  it("requests enough results for the scrollable menu", async () => {
    renderSearch();
    await userEvent.type(screen.getByLabelText("Global search"), "ma");
    await screen.findByText("Maverick");
    const call = get.mock.calls.find((c) => c[0] === "/v1/search");
    expect((call![1] as any).params.query.limit).toBe(25);
    expect(screen.getByRole("listbox", { name: "Search results" })).toHaveClass("dz-search-menu");
  });
});
