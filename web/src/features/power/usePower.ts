import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { qk } from "@/lib/queryKeys";

export type PowerRanking = components["schemas"]["PowerRanking"];

async function fetchPower(seasonId: number, throughWeek?: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/power", {
    params: {
      path: { season_id: seasonId },
      query: throughWeek != null ? { through_week: throughWeek } : undefined,
    },
  });
  if (error || !data) throw new Error("Failed to load power ranking");
  return data.data;
}

async function fetchPowerTimeline(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/power/timeline", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load power timeline");
  return data.data;
}

/** Power ranking for a season, optionally as-of a week (omit for the latest). */
export function usePower(seasonId: number | undefined, throughWeek?: number, enabled = true) {
  return useQuery({
    queryKey: seasonId ? qk.power(seasonId, throughWeek) : ["power", "none"],
    queryFn: () => fetchPower(seasonId as number, throughWeek),
    enabled: enabled && seasonId != null,
  });
}

/** Power rank + score per team per regular-season week (the RankFlow trajectory). */
export function usePowerTimeline(seasonId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: seasonId ? qk.powerTimeline(seasonId) : ["power", "none", "timeline"],
    queryFn: () => fetchPowerTimeline(seasonId as number),
    enabled: enabled && seasonId != null,
  });
}
