import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SeasonProvider } from "@/app/shell/SeasonContext";
import { renderWithProviders } from "@/test/render";

import { InsightsLabPage } from "./InsightsLabPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const SEASON_LIST = [{ season_id: 7, season_year: 2024, is_scored: true, status: "completed" }];

const INSIGHTS = {
  season_id: 7,
  season_year: 2024,
  available: true,
  notes: ["ADP coverage is limited this season — read it as a soft signal."],
  insights: [
    {
      kind: "schedule_luck",
      title: "Schedule luck — 2024",
      narration: "In 2024, Alpha was the league's unluckiest manager.",
      facts: [
        { label: "Actual wins", value: 6, unit: null },
        { label: "Expected (all-play) wins", value: 8.4, unit: null },
        { label: "Luck gap", value: 2.4, unit: "wins" },
      ],
      subject: { owner_id: 1, owner_name: "Alpha" },
      provenance: { metric: "standings.schedule_luck", endpoint: "/v1/seasons/7/standings/insights" },
      confidence: "high",
    },
    {
      kind: "draft_market",
      title: "Biggest reach — 2024 draft",
      narration: "The draft's biggest reach: Bravo Player went #1 overall.",
      facts: [{ label: "Drafted at", value: 1, unit: "overall" }],
      subject: { owner_id: 2, owner_name: "Bravo" },
      provenance: { metric: "draft.market_axis", endpoint: "/v1/seasons/7/draft/value" },
      confidence: "medium",
    },
  ],
};

function mockEndpoints(insights: unknown = INSIGHTS) {
  mockGet.mockImplementation((path: string) => {
    if (path === "/v1/seasons") return Promise.resolve({ data: { data: { seasons: SEASON_LIST }, meta: {} } });
    if (path === "/v1/lab/insights/{season_id}") return Promise.resolve({ data: { data: insights, meta: {} } });
    return Promise.resolve({ error: { detail: "unexpected" } });
  });
}

beforeEach(() => mockGet.mockReset());

describe("InsightsLabPage", () => {
  it("renders an insight card per primitive: narration, facts, provenance, confidence", async () => {
    mockEndpoints();
    renderWithProviders(
      <SeasonProvider>
        <InsightsLabPage />
      </SeasonProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Insights Lab" })).toBeInTheDocument();
    // Both primitives render as cards.
    expect(await screen.findByText("Schedule luck — 2024")).toBeInTheDocument();
    expect(screen.getByText("Biggest reach — 2024 draft")).toBeInTheDocument();
    // The narration prose and a traceable fact both appear.
    expect(screen.getByText(/unluckiest manager/)).toBeInTheDocument();
    expect(screen.getByText("Expected (all-play) wins")).toBeInTheDocument();
    // Confidence tag + season-level honesty note are surfaced.
    expect(screen.getByText("high confidence")).toBeInTheDocument();
    expect(screen.getByText(/coverage is limited/)).toBeInTheDocument();
    // Provenance is shown so a claim is traceable to a view.
    expect(screen.getByText(/standings.schedule_luck/)).toBeInTheDocument();
  });

  it("shows an honest empty state when no primitive fires", async () => {
    mockEndpoints({ season_id: 7, season_year: 2024, available: false, insights: [], notes: [] });
    renderWithProviders(
      <SeasonProvider>
        <InsightsLabPage />
      </SeasonProvider>,
    );
    expect(await screen.findByText("No insights for this season yet")).toBeInTheDocument();
  });
});
