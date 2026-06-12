import { describe, expect, it } from "vitest";

import { deriveSeasonPhase } from "./seasonPhase";

describe("deriveSeasonPhase", () => {
  it("treats a completed current season as offseason (between seasons)", () => {
    const phase = deriveSeasonPhase({
      current: { season_id: 2, season_year: 2025, status: "completed", is_scored: true },
      seasons: [{ season_id: 2, season_year: 2025, status: "completed", is_scored: true }],
    });
    expect(phase.phase).toBe("offseason");
    expect(phase.reason).toBe("completed");
    expect(phase.lastCompletedSeason?.season_year).toBe(2025);
  });

  it("treats an in-progress current season as inseason", () => {
    const phase = deriveSeasonPhase({
      current: { season_id: 3, season_year: 2026, status: "in_progress", is_scored: true },
      seasons: [
        { season_id: 3, season_year: 2026, status: "in_progress", is_scored: true },
        { season_id: 2, season_year: 2025, status: "completed", is_scored: true },
      ],
    });
    expect(phase.phase).toBe("inseason");
    expect(phase.reason).toBe("in_progress");
    expect(phase.lastCompletedSeason?.season_year).toBe(2026);
  });

  it("falls back to the latest scored season when there is no current season", () => {
    const phase = deriveSeasonPhase({
      current: null,
      seasons: [{ season_id: 2, season_year: 2025, status: "completed", is_scored: true }],
    });
    expect(phase.phase).toBe("offseason");
    expect(phase.reason).toBe("no_current");
    expect(phase.lastCompletedSeason?.season_year).toBe(2025);
  });
});
