import { useQuery } from "@tanstack/react-query";

import { Card, CardHeader, DataGap, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { capabilityGapText } from "@/lib/platform";
import { qk } from "@/lib/queryKeys";

async function fetchPickLedger() {
  const { data, error } = await api.GET("/v1/league/picks");
  if (error || !data) throw new Error("Failed to load the pick ledger");
  return data.data;
}

/** Traded future draft picks and who owns them now (Sleeper D6). League-wide, not per season. */
export function PickLedgerCard({ platform }: { platform: string | null | undefined }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.pickLedger(),
    queryFn: fetchPickLedger,
  });
  return (
    <Card>
      <CardHeader eyebrow="future draft picks" title="Pick ledger" />
      {isLoading && <Skeleton className="m-5 h-24" />}
      {isError && <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />}
      {data && !data.available && (
        <div className="p-5">
          <DataGap reason={capabilityGapText(data.reason ?? "traded_future_picks", null, platform)} />
        </div>
      )}
      {data?.available && data.picks.length === 0 && (
        <p className="px-5 pb-4 text-[var(--fs-sm)] text-faint">No future picks have changed hands.</p>
      )}
      {data?.available && data.picks.length > 0 && (
        <div className="overflow-x-auto">
          <table className="dz-table">
            <thead>
              <tr>
                <th>Pick</th>
                <th>Original owner</th>
                <th>Now owned by</th>
                <th>Previously</th>
              </tr>
            </thead>
            <tbody>
              {data.picks.map((p, i) => (
                <tr key={i}>
                  <td className="num">
                    {p.pick_season} R{p.round}
                  </td>
                  <td>{p.original_owner?.owner_name ?? "—"}</td>
                  <td className="font-semibold">{p.current_owner?.owner_name ?? "—"}</td>
                  <td className="text-muted">{p.previous_owner?.owner_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
