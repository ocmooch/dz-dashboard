import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

export type SeasonInfo = {
  season_id: number;
  season_year: number;
  status?: string | null;
  is_scored: boolean;
  champion?: { owner_name?: string | null; team_name?: string | null } | null;
};

type SeasonCtx = {
  seasons: SeasonInfo[];
  current: SeasonInfo | null;
  setSeasonId: (id: number) => void;
  isLoading: boolean;
};

const Ctx = createContext<SeasonCtx | null>(null);

async function fetchSeasons(): Promise<SeasonInfo[]> {
  const { data, error } = await api.GET("/v1/seasons");
  if (error || !data) throw new Error("Failed to load seasons");
  return data.data.seasons as SeasonInfo[];
}

export function SeasonProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useQuery({ queryKey: qk.seasons, queryFn: fetchSeasons });
  const seasons = useMemo(
    () => [...(data ?? [])].sort((a, b) => b.season_year - a.season_year),
    [data],
  );
  const [seasonId, setSeasonId] = useState<number | null>(null);

  useEffect(() => {
    if (seasonId === null && seasons.length > 0) setSeasonId(seasons[0].season_id);
  }, [seasons, seasonId]);

  const current = seasons.find((s) => s.season_id === seasonId) ?? seasons[0] ?? null;

  return (
    <Ctx.Provider value={{ seasons, current, setSeasonId, isLoading }}>{children}</Ctx.Provider>
  );
}

export function useSeasons(): SeasonCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSeasons must be used within SeasonProvider");
  return ctx;
}
