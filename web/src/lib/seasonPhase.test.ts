import { describe, expect, it } from "vitest";

import { deriveSeasonPhase } from "./seasonPhase";

describe("deriveSeasonPhase", () => {
  it("treats an unscored current season with prior scored seasons as offseason", () => {
    const phase = deriveSeasonPhase({
      current: { season_id: 3, season_year: 2026, is_scored: false },
      seasons: [
        { season_id: 3, season_year: 2026, is_scored: false },
        { season_id: 2, season_year: 2025, is_scored: true },
      ],
    });
    expect(phase.phase).toBe("offseason");
    expect(phase.lastCompletedSeason?.season_year).toBe(2025);
  });

  it("treats a scored current season as inseason without reading status", () => {
    const phase = deriveSeasonPhase({
      current: { season_id: 2, season_year: 2025, is_scored: true },
      seasons: [{ season_id: 2, season_year: 2025, is_scored: true }],
    });
    expect(phase.phase).toBe("inseason");
    expect(phase.reason).toBe("current_scored");
  });
});
