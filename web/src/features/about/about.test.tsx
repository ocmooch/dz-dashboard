import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AboutPage } from "./AboutPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const META = {
  latest_run: {
    run_id: 42,
    status: "success",
    mode: "incremental",
    started_at: "2025-09-01T10:00:00Z",
    finished_at: "2025-09-01T10:05:00Z",
  },
  coverage: {
    seasons_present: [2010, 2011, 2012, 2024, 2025],
    seasons_scored: [2016, 2017, 2024, 2025],
    scored_year_min: 2016,
    scored_year_max: 2025,
    reconstruction_complete: true,
    availability_current_season_only: true,
    dst_scoring_complete: false,
  },
};

function renderAbout() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AboutPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockResolvedValue(envelope(META));
});

afterEach(() => vi.clearAllMocks());

describe("AboutPage", () => {
  it("renders coverage ranges sourced from /v1/meta", async () => {
    renderAbout();
    expect(await screen.findByText("2010–2025")).toBeInTheDocument(); // seasons present
    expect(screen.getAllByText("2016–2025").length).toBeGreaterThan(0); // scored range
  });

  it("reports reconstruction status and the latest run", async () => {
    renderAbout();
    expect(await screen.findByText("complete")).toBeInTheDocument();
    expect(screen.getByText("#42")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
  });

  it("surfaces the documented gaps honestly (availability + DST)", async () => {
    renderAbout();
    expect(await screen.findByText("current season only")).toBeInTheDocument();
    expect(screen.getByText("not scored")).toBeInTheDocument();
  });

  it("shows nflverse + Sleeper attribution", async () => {
    renderAbout();
    expect(await screen.findByText("nflverse")).toBeInTheDocument();
    expect(screen.getByText("Sleeper")).toBeInTheDocument();
    expect(screen.getByText(/CC.?BY.?4.0/i)).toBeInTheDocument();
  });
});
