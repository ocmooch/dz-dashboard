import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Button, Card, CardHeader, Chip, EmptyState, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

const POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"] as const;
const PAGE_SIZE = 50;

type Filters = {
  name: string;
  position: string;
  nfl_team: string;
  active: string; // "", "true", "false"
  offset: number;
};

async function fetchPlayers(f: Filters) {
  const { data, error } = await api.GET("/v1/players", {
    params: {
      query: {
        name: f.name || undefined,
        position: f.position || undefined,
        nfl_team: f.nfl_team || undefined,
        active: f.active === "" ? undefined : f.active === "true",
        limit: PAGE_SIZE,
        offset: f.offset,
      },
    },
  });
  if (error || !data) throw new Error("Failed to load players");
  return data.data;
}

export function PlayersPage() {
  const [params, setParams] = useSearchParams();
  const filters: Filters = {
    name: params.get("name") ?? "",
    position: params.get("position") ?? "",
    nfl_team: params.get("nfl_team") ?? "",
    active: params.get("active") ?? "",
    offset: Math.max(0, Number(params.get("offset") ?? "0") || 0),
  };

  // Any filter change resets paging; offset moves on its own.
  const set = (patch: Partial<Filters>, resetOffset = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === "" || v == null) next.delete(k);
      else next.set(k, String(v));
    }
    if (resetOffset && !("offset" in patch)) next.delete("offset");
    setParams(next, { replace: true });
  };

  const { data, isLoading, isError, refetch, isPlaceholderData } = useQuery({
    queryKey: qk.players(filters as unknown as Record<string, unknown>),
    queryFn: () => fetchPlayers(filters),
    placeholderData: keepPreviousData,
  });

  const players = data?.players ?? [];
  const page = Math.floor(filters.offset / PAGE_SIZE) + 1;
  const atEnd = players.length < PAGE_SIZE;

  return (
    <div className="dz-rise space-y-4">
      <div>
        <div className="dz-eyebrow mb-1">explore</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Players</h1>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            className="dz-input min-w-[200px] flex-1"
            type="search"
            placeholder="Search by name…"
            aria-label="Search players by name"
            value={filters.name}
            onChange={(e) => set({ name: e.target.value })}
          />
          <select
            className="dz-select"
            aria-label="Filter by position"
            value={filters.position}
            onChange={(e) => set({ position: e.target.value })}
          >
            <option value="">All positions</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <input
            className="dz-input w-28"
            type="text"
            placeholder="NFL team"
            aria-label="Filter by NFL team"
            value={filters.nfl_team}
            onChange={(e) => set({ nfl_team: e.target.value.toUpperCase() })}
          />
          <select
            className="dz-select"
            aria-label="Filter by active status"
            value={filters.active}
            onChange={(e) => set({ active: e.target.value })}
          >
            <option value="">Active &amp; retired</option>
            <option value="true">Active only</option>
            <option value="false">Retired only</option>
          </select>
        </div>
      </Card>

      <Card>
        <CardHeader
          eyebrow={`page ${page}`}
          title="Index"
          action={
            <div className="inline-flex items-center gap-2">
              <Button
                variant="ghost"
                aria-label="Previous page"
                disabled={filters.offset === 0 || isPlaceholderData}
                onClick={() => set({ offset: Math.max(0, filters.offset - PAGE_SIZE) }, false)}
              >
                ‹
              </Button>
              <Button
                variant="ghost"
                aria-label="Next page"
                disabled={atEnd || isPlaceholderData}
                onClick={() => set({ offset: filters.offset + PAGE_SIZE }, false)}
              >
                ›
              </Button>
            </div>
          }
        />
        {isLoading && (
          <div className="space-y-2 p-5">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        )}
        {isError && (
          <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
        )}
        {data && players.length === 0 && (
          <EmptyState title="No players match" hint="Loosen a filter or clear the search." />
        )}
        {data && players.length > 0 && (
          <div className="overflow-x-auto">
            <table className="dz-table">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Pos</th>
                  <th>NFL</th>
                </tr>
              </thead>
              <tbody>
                {players.map((p) => (
                  <tr key={p.player_id}>
                    <td>
                      <Link to={`/players/${p.player_id}`} className="hover:text-accent">
                        <Chip name={p.name_full} />
                      </Link>
                    </td>
                    <td className="text-muted">{p.position ?? "—"}</td>
                    <td className="text-muted">{p.nfl_team ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
