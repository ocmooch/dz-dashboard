import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { type PlayerStatusTimeline, StatusTimelineView } from "./StatusTimeline";

const sleeper = (over: Partial<PlayerStatusTimeline> = {}): PlayerStatusTimeline => ({
  player_id: 1,
  season_year: 2026,
  platform: "sleeper",
  platform_label: "Sleeper",
  available: true,
  reason: null,
  has_snapshots: true,
  snapshot_capability: { state: "available", note: null },
  is_provisional: true,
  latest: null,
  weeks: [
    {
      week: 7,
      kickoff_date: "2026-10-22",
      game_report: {
        source: "nflverse",
        as_of: null,
        injury_status: "Doubtful",
        injury_body_part: "Ankle",
      },
      game_report_gap: null,
      snapshot: { source: "sleeper", as_of: "2026-10-21", roster_status: "IR", depth_chart: "WR2" },
      snapshot_gap: null,
    },
    {
      week: 8,
      kickoff_date: "2026-10-29",
      game_report: null,
      game_report_gap: null,
      snapshot: null,
      snapshot_gap: "stale_or_missing_snapshot",
    },
    {
      week: 9,
      kickoff_date: "2026-11-05",
      game_report: null,
      game_report_gap: "reports_not_loaded",
      snapshot: null,
      snapshot_gap: "stale_or_missing_snapshot",
    },
  ],
  ...over,
});

describe("StatusTimelineView", () => {
  it("shows the report badge, the snapshot roster status and both gap kinds", () => {
    render(<StatusTimelineView data={sleeper()} />);
    expect(screen.getByText("Sleeper snapshot")).toBeInTheDocument();
    expect(screen.getByText("D · Ankle")).toBeInTheDocument();
    expect(screen.getByText("IR · WR2")).toBeInTheDocument();
    expect(screen.getAllByText("No status capture within 7 days of kickoff")).toHaveLength(2);
    expect(screen.getByText("Injury report not loaded for this week yet")).toBeInTheDocument();
    expect(screen.getByText(/subject to change/)).toBeInTheDocument();
  });

  it("renders not-on-report as a dash, not a gap", () => {
    render(<StatusTimelineView data={sleeper()} />);
    const wk8 = screen.getByText("wk8").closest("tr")!;
    expect(within(wk8).getByTitle("Not on that week's injury report")).toHaveTextContent("—");
  });

  it("hides the snapshot column on a legacy season", () => {
    render(
      <StatusTimelineView
        data={sleeper({
          platform: "nfl_com",
          platform_label: "NFL.com",
          has_snapshots: false,
          is_provisional: false,
          snapshot_capability: { state: "partial", note: "Weekly injury reports only." },
          weeks: [
            {
              week: 1,
              kickoff_date: "2017-09-07",
              game_report: null,
              game_report_gap: null,
              snapshot: null,
              snapshot_gap: null,
            },
          ],
        })}
      />,
    );
    expect(screen.queryByText(/snapshot/i)).toBeNull();
    expect(screen.queryByText("No status capture within 7 days of kickoff")).toBeNull();
    expect(screen.getByText("Weekly injury reports only.")).toBeInTheDocument();
  });

  it("shows the latest card when present, with the snapshot date in the tooltip", () => {
    render(
      <StatusTimelineView
        data={sleeper({
          latest: { source: "sleeper", as_of: "2026-11-04", injury_status: "Questionable" },
        })}
      />,
    );
    const latest = screen.getByTestId("status-latest");
    expect(within(latest).getByText("Q")).toHaveAttribute(
      "title",
      "Questionable. Sleeper status as of 2026-11-04, before kickoff.",
    );
  });

  it("shows a season-level gap when the season has no games", () => {
    render(
      <StatusTimelineView data={sleeper({ available: false, reason: "season_not_played", weeks: [] })} />,
    );
    expect(screen.getByText("This season has no games yet")).toBeInTheDocument();
  });
});
