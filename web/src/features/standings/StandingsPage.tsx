import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { RankFlow } from "@/charts";
import { Badge, Card, CardHeader, Chip, ErrorState, RecordLine, Skeleton, Trophy } from "@/design-system";
import { api } from "@/lib/api/client";
import { num, ordinal, pct } from "@/lib/format";
import { qk } from "@/lib/queryKeys";
import { toRankFlow } from "@/lib/rankflow";

async function fetchStandings(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/standings", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load standings");
  return data.data;
}

async function fetchTimeline(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/standings/timeline", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load standings timeline");
  return data.data;
}

function StreakCell({ streak }: { streak: { result?: string | null; length?: number } }) {
  if (!streak.result) return <span className="text-faint">—</span>;
  const tone = streak.result === "W" ? "text-win" : streak.result === "L" ? "text-loss" : "text-muted";
  return (
    <span className={`num ${tone}`}>
      {streak.result}
      {streak.length}
    </span>
  );
}

function PlacementCell({ finalRank }: { finalRank: number | null | undefined }) {
  if (finalRank == null) return <span className="text-faint">—</span>;
  if (finalRank === 1) return <Trophy label="Champion" />;
  return <span className="num text-accent">{ordinal(finalRank)}</span>;
}

export function StandingsPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: seasonId ? qk.standings(seasonId) : ["standings", "none"],
    queryFn: () => fetchStandings(seasonId as number),
    enabled: seasonId != null,
  });
  const timeline = useQuery({
    queryKey: seasonId ? qk.standingsTimeline(seasonId) : ["standings", "none", "timeline"],
    queryFn: () => fetchTimeline(seasonId as number),
    enabled: seasonId != null,
  });

  const flow = timeline.data ? toRankFlow(timeline.data.teams) : null;
  const showFinalPlacement = data?.rows.some((r) => r.final_rank != null) ?? false;

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Standings</h1>
        </div>
        {data && (
          <Badge variant={data.rank_basis === "final_rank" ? "default" : "accent"}>
            order: {data.rank_basis === "final_rank" ? "official (NFL.com)" : "computed · wins→PF"}
          </Badge>
        )}
      </div>

      {data?.tiebreak_caveat && (
        <Badge variant="gap">historical tiebreak may differ from NFL.com for this era</Badge>
      )}

      <Card>
        <CardHeader eyebrow="regular season" title="Table" />
        {isLoading && (
          <div className="space-y-2 p-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        )}
        {isError && <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />}
        {data && (
          <div className="overflow-x-auto">
            <table className="dz-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Manager</th>
                  <th className="dz-num">Record</th>
                  <th className="dz-num">Win%</th>
                  <th className="dz-num">PF</th>
                  <th className="dz-num">PA</th>
                  {showFinalPlacement && <th className="dz-num">Finish</th>}
                  <th className="dz-num">Streak</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.team_id}>
                    <td className="num text-faint">{r.rank}</td>
                    <td>
                      <Link to={`/teams/${r.team_id}`} className="hover:text-accent">
                        <Chip name={r.owner_name} sub={r.team_name ?? undefined} />
                      </Link>
                    </td>
                    <td className="dz-num">
                      <RecordLine wins={r.wins} losses={r.losses} ties={r.ties} />
                    </td>
                    <td className="dz-num text-muted">{pct(r.win_pct)}</td>
                    <td className="dz-num">{num(r.points_for)}</td>
                    <td className="dz-num text-muted">{num(r.points_against)}</td>
                    {showFinalPlacement && (
                      <td className="dz-num">
                        <PlacementCell finalRank={r.final_rank} />
                      </td>
                    )}
                    <td className="dz-num">
                      <StreakCell streak={r.streak} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader eyebrow="rank by week" title="Standings over time" />
        <div className="p-5">
          {timeline.isLoading && <Skeleton className="h-[280px] w-full" />}
          {flow && flow.data.length > 0 ? (
            <RankFlow
              title="Standings by week (rank 1 on top)"
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
