import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { Heatmap } from "@/charts";
import { Badge, Card, CardHeader, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

async function fetchRivalryMatrix() {
  const { data, error } = await api.GET("/v1/owners/rivalry-matrix");
  if (error || !data) throw new Error("Failed to load rivalry matrix");
  return data.data;
}

export function RivalriesPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.rivalryMatrix,
    queryFn: fetchRivalryMatrix,
  });

  // The matrix is a presentation transform only: owners give the axes, and each
  // cell's win-pct (0–1) becomes a 0–100 heat value. null (never met / out of
  // coverage) passes straight through so the Heatmap can render an honest gap.
  const owners = data?.owners ?? [];
  const indexOf = new Map(owners.map((o, i) => [o.owner_id, i]));
  const labels = owners.map((o) => o.display_name ?? `#${o.owner_id}`);
  const values: (number | null)[][] = owners.map(() => owners.map(() => null));
  for (const cell of data?.cells ?? []) {
    const r = indexOf.get(cell.a);
    const c = indexOf.get(cell.b);
    if (r === undefined || c === undefined) continue;
    values[r][c] = cell.a_win_pct == null ? null : Math.round(cell.a_win_pct * 100);
  }

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">All-time</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Rivalries</h1>
        </div>
        <Badge variant="accent">win % · row vs column</Badge>
      </div>

      <Card>
        <CardHeader eyebrow="head-to-head" title="Rivalry Matrix" />
        <div className="p-5">
          {isLoading && <Skeleton className="h-64 w-full" />}
          {isError && (
            <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
          )}
          {data && (
            <>
              <Heatmap
                title="Rivalry win-percentage matrix"
                rows={labels}
                cols={labels}
                values={values}
                onSelect={(r, c) =>
                  navigate(`/rivalries/${owners[r].owner_id}/vs/${owners[c].owner_id}`)
                }
              />
              <p className="mt-4 text-[var(--fs-xs)] text-faint">
                Each cell is the row manager&apos;s all-time win rate against the column manager
                (regular season + playoffs). Click any cell for the full pairwise history. Pairs
                that never met show a gap, never a zero.
              </p>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
