import { api } from "@/lib/api/client";

/** `/v1/seasons/current` (Sleeper D3): the in-progress season, or `available: false` off-season. */
export async function fetchCurrentSeason() {
  const { data, error } = await api.GET("/v1/seasons/current");
  if (error || !data) throw new Error("current season");
  return data.data;
}
