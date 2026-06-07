import type { SeasonInfo } from "@/app/shell/SeasonContext";

export type SeasonPhase = {
  phase: "offseason" | "inseason";
  currentSeason: SeasonInfo | null;
  lastCompletedSeason: SeasonInfo | null;
  reason: "current_unscored" | "current_scored" | "no_current";
};

export function deriveSeasonPhase({
  current,
  seasons,
}: {
  current: SeasonInfo | null;
  seasons: SeasonInfo[];
}): SeasonPhase {
  const scored = [...seasons].filter((s) => s.is_scored).sort((a, b) => b.season_year - a.season_year);
  if (!current) {
    return { phase: "offseason", currentSeason: null, lastCompletedSeason: scored[0] ?? null, reason: "no_current" };
  }
  if (!current.is_scored && scored.length > 0) {
    return { phase: "offseason", currentSeason: current, lastCompletedSeason: scored[0], reason: "current_unscored" };
  }
  return { phase: "inseason", currentSeason: current, lastCompletedSeason: scored[0] ?? current, reason: "current_scored" };
}
