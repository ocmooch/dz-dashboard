import { useQuery } from "@tanstack/react-query";

import { useSeasons } from "@/app/shell/SeasonContext";
import { RankFlow } from "@/charts";
import { Badge, Card, CardHeader, Chip, ErrorState, RecordLine, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { num, pct } from "@/lib/format";
import { qk } from "@/lib/queryKeys";
import { toRankFlow } from "@/lib/rankflow";

async function fetchPower(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/power", {
    params: { path: { season_id: seasonId } },
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

/** Movement of the model's rank vs the plain standings rank. Positive = the model
 *  rates the team above its record (a riser); negative = a faller. */
function DeltaTag({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-faint">—</span>;
  const tone = delta > 0 ? "win" : "loss";
  return (
    <Badge variant={tone}>
      {delta > 0 ? `▲ ${delta}` : `▼ ${Math.abs(delta)}`}
    </Badge>
  );
}

export function PowerPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;

  const power = useQuery({
    queryKey: seasonId ? qk.power(seasonId) : ["power", "none"],
    queryFn: () => fetchPower(seasonId as number),
    enabled: seasonId != null,
  });
  const timeline = useQuery({
    queryKey: seasonId ? qk.powerTimeline(seasonId) : ["power", "none", "timeline"],
    queryFn: () => fetchPowerTimeline(seasonId as number),
    enabled: seasonId != null,
  });

  const flow = timeline.data ? toRankFlow(timeline.data.teams) : null;

  return (
    <div className="dz-rise space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">
            Power Ranking
          </h1>
        </div>
        {power.data && (
          <Badge variant="accent">
            through week {power.data.through_week}
          </Badge>
        )}
      </div>

      {power.isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => power.refetch()} />
      )}

      <Card>
        <CardHeader eyebrow="model · scoring over luck" title="This week" />
        {power.isLoading && (
          <div className="space-y-2 p-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        )}
        {power.data && (
          <div className="overflow-x-auto">
            <table className="dz-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Manager</th>
                  <th className="dz-num">Power</th>
                  <th className="dz-num">Record</th>
                  <th className="dz-num">PF/g</th>
                  <th className="dz-num">Win%</th>
                  <th className="dz-num">Last 3 PF/g</th>
                  <th className="dz-num">vs standings</th>
                </tr>
              </thead>
              <tbody>
                {power.data.rows.map((r) => (
                  <tr key={r.team_id}>
                    <td className="num text-faint">{r.rank}</td>
                    <td>
                      <Chip name={r.owner_name} sub={r.team_name ?? undefined} />
                    </td>
                    <td className="dz-num font-semibold text-accent">{num(r.power_score)}</td>
                    <td className="dz-num">
                      <RecordLine wins={r.wins} losses={r.losses} ties={r.ties} />
                    </td>
                    <td className="dz-num">{num(r.points_for_per_game)}</td>
                    <td className="dz-num text-muted">{pct(r.win_pct)}</td>
                    <td className="dz-num text-muted">{num(r.recent_points_for_per_game)}</td>
                    <td className="dz-num">
                      <DeltaTag delta={r.rank_delta} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {power.data?.explainer && (
          <p className="max-w-prose p-5 pt-3 text-[var(--fs-xs)] text-faint">
            <span className="dz-eyebrow">How this is computed · </span>
            {power.data.explainer}
          </p>
        )}
      </Card>

      <Card>
        <CardHeader eyebrow="rank by week" title="Power over time" />
        <div className="p-5">
          {timeline.isLoading && <Skeleton className="h-[280px] w-full" />}
          {flow && flow.data.length > 0 ? (
            <RankFlow
              title="Power ranking by week (rank 1 on top)"
              data={flow.data}
              series={flow.series}
              xKey="week"
              xLabel="Week"
              teamCount={flow.teamCount}
              height={300}
            />
          ) : (
            !timeline.isLoading && (
              <p className="text-[var(--fs-sm)] text-faint">No weekly data for this season yet.</p>
            )
          )}
        </div>
      </Card>
    </div>
  );
}
