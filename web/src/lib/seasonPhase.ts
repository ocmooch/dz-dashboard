import type { SeasonInfo } from "@/app/shell/SeasonContext";

export type SeasonPhase = {
  phase: "offseason" | "inseason";
  currentSeason: SeasonInfo | null;
  lastCompletedSeason: SeasonInfo | null;
  /** The newest season that is over (not in progress): the one whose champion Home names. */
  lastFinishedSeason: SeasonInfo | null;
  reason: "in_progress" | "completed" | "no_current";
};

/**
 * Decide whether the league is mid-season or in the off-season, and surface the
 * most recent completed season the home page should summarize.
 *
 * The dashboard hides upcoming seasons that have not played a game yet, so the
 * current (latest displayed) season is the truthful phase signal: a season still
 * marked `in_progress` means games are being played (in-season); any other
 * status — typically `completed` — means we are between seasons (off-season).
 * This reads `status`, never the year, so it stays correct as seasons roll over.
 */
export function deriveSeasonPhase({
  current,
  seasons,
}: {
  current: SeasonInfo | null;
  seasons: SeasonInfo[];
}): SeasonPhase {
  const scored = [...seasons].filter((s) => s.is_scored).sort((a, b) => b.season_year - a.season_year);
  // An in-progress season has no champion yet, even once it is scored (live 2026 after go-live).
  const lastFinishedSeason =
    [...seasons].filter((s) => s.status !== "in_progress").sort((a, b) => b.season_year - a.season_year)[0] ??
    null;
  if (!current) {
    return {
      phase: "offseason",
      currentSeason: null,
      lastCompletedSeason: scored[0] ?? null,
      lastFinishedSeason,
      reason: "no_current",
    };
  }
  if (current.status === "in_progress") {
    return {
      phase: "inseason",
      currentSeason: current,
      lastCompletedSeason: scored[0] ?? current,
      lastFinishedSeason,
      reason: "in_progress",
    };
  }
  return {
    phase: "offseason",
    currentSeason: current,
    lastCompletedSeason: scored[0] ?? current,
    lastFinishedSeason,
    reason: "completed",
  };
}
