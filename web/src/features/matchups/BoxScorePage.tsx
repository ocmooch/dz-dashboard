import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { StackedBreakdown, type ChartRow, type SeriesDef } from "@/charts";
import { Badge, Card, CardHeader, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type BoxScore = Awaited<ReturnType<typeof fetchBoxScore>>;
type BoxTeam = NonNullable<BoxScore["home"]>;
type BoxPlayer = BoxTeam["lineup"][number];

async function fetchBoxScore(matchupId: number) {
  const { data, error } = await api.GET("/v1/matchups/{matchup_id}/box-score", {
    params: { path: { matchup_id: matchupId } },
  });
  if (error || !data) throw new Error("Failed to load box score");
  return data.data;
}

/** Injured-reserve slots carry an explicit "IR" label; everything else with no
 *  stat line (BYE / inactive / scratch) is shown as a neutral em dash. */
function isIR(slot: string | null | undefined): boolean {
  return !!slot && slot.toUpperCase().startsWith("IR");
}

function shortName(name: string | null | undefined): string {
  if (!name) return "—";
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 ? `${parts[0][0]}. ${parts[parts.length - 1]}` : name;
}

/** Shape the already-computed per-player breakdowns into stacked-bar rows.
 *  Pure presentation — no metric is computed here, only rearranged. */
function breakdownChart(starters: BoxPlayer[]): { rows: ChartRow[]; series: SeriesDef[] } {
  const keys = new Set<string>();
  for (const p of starters) {
    for (const k of Object.keys(p.breakdown ?? {})) keys.add(k);
  }
  const series: SeriesDef[] = [...keys].map((key) => ({ key, label: key }));
  const rows: ChartRow[] = starters.map((p) => {
    const row: ChartRow = { player: shortName(p.player_name) };
    for (const key of keys) {
      const v = (p.breakdown as Record<string, unknown>)?.[key];
      row[key] = typeof v === "number" ? v : 0;
    }
    return row;
  });
  return { rows, series };
}

function LineupTable({ team }: { team: BoxTeam }) {
  const starters = team.lineup.filter((p) => p.is_starter);
  const bench = team.lineup.filter((p) => !p.is_starter);
  return (
    <table className="dz-table">
      <thead>
        <tr>
          <th>Slot</th>
          <th>Player</th>
          <th className="dz-num">Proj</th>
          <th className="dz-num">Pts</th>
        </tr>
      </thead>
      <tbody>
        {starters.map((p) => (
          <PlayerRow key={p.player_id} p={p} />
        ))}
        {bench.length > 0 && (
          <tr>
            <td colSpan={4} className="dz-eyebrow pt-3 text-faint">
              bench
            </td>
          </tr>
        )}
        {bench.map((p) => (
          <PlayerRow key={p.player_id} p={p} muted />
        ))}
      </tbody>
    </table>
  );
}

/** Render a league-points value, explaining a 0 when there's context:
 *  a bye / did-not-play status reason, a flagged "unexpectedly 0", or — for an
 *  organic 0 (played, scored nothing) — just the bare number with no fuss. */
function ScoreCell({ p, muted }: { p: BoxPlayer; muted?: boolean }) {
  const value = num(p.league_points);
  if (p.zero_reason === "bye" || p.zero_reason === "did_not_play") {
    const tag = p.zero_reason === "bye" ? "BYE" : "DNP";
    const title =
      p.zero_reason === "bye" ? "On bye — did not play" : "Did not play (inactive / injury)";
    return (
      <span className="inline-flex items-center justify-end gap-1.5" title={title}>
        <span className="text-faint">{value}</span>
        <span className="dz-eyebrow text-faint">{tag}</span>
      </span>
    );
  }
  if (p.zero_reason === "unexpected") {
    return (
      <span
        className="inline-flex items-center justify-end gap-1 text-loss"
        title={p.zero_detail ?? "Unexpectedly 0 — reason unclear"}
      >
        {value}
        <span aria-label="unexpectedly zero" className="dz-eyebrow">
          ⚠
        </span>
      </span>
    );
  }
  // Normal points — includes an organic 0.0 (played, scored nothing). Never a fake blank.
  return <span className={muted ? "text-muted" : "text-text"}>{value}</span>;
}

function PlayerRow({ p, muted = false }: { p: BoxPlayer; muted?: boolean }) {
  return (
    <tr>
      <td className="num text-faint">{p.roster_slot ?? "—"}</td>
      <td className={muted ? "text-muted" : undefined}>
        {p.player_name ?? "—"}
        <span className="ml-1 text-[var(--fs-xs)] text-faint">{p.position}</span>
      </td>
      <td className="dz-num text-faint">{p.projection != null ? num(p.projection) : "—"}</td>
      <td className="dz-num">
        {!p.available ? (
          // Pipeline explicitly flagged this entry as a gap (e.g. a known scoring hole).
          <DataGap reason={p.reason ?? undefined} size="sm" />
        ) : p.league_points != null ? (
          <ScoreCell p={p} muted={muted} />
        ) : (
          // No stat line: a legitimate absence (IR / BYE / inactive), not a data gap.
          <span className="text-faint">{isIR(p.roster_slot) ? "IR" : "—"}</span>
        )}
      </td>
    </tr>
  );
}

function TeamColumn({ team, isWinner }: { team: BoxTeam; isWinner: boolean }) {
  const starters = team.lineup.filter((p) => p.is_starter);
  const { rows, series } = breakdownChart(starters);
  return (
    <Card>
      <CardHeader
        eyebrow={team.owner_name ?? undefined}
        title={team.team_name ?? "—"}
        action={
          <span className={`num text-[var(--fs-h1)] font-bold ${isWinner ? "text-win" : "text-muted"}`}>
            {num(team.total_score)}
          </span>
        }
      />
      <div className="grid grid-cols-2 gap-4 p-5 sm:grid-cols-4">
        <Stat label="Starters" value={num(team.starter_points)} />
        <Stat label="Bench" value={num(team.bench_points)} tone="default" />
        <Stat label="Optimal" value={num(team.optimal_total)} tone="accent" />
        <Stat label="Left on bench" value={num(team.points_left_on_bench)} tone="loss" />
      </div>
      {team.beat_projection_by != null && (
        <div className="px-5 pb-2">
          <Badge variant={team.beat_projection_by >= 0 ? "win" : "loss"}>
            {team.beat_projection_by >= 0 ? "beat projection by " : "under projection by "}
            {num(Math.abs(team.beat_projection_by))}
          </Badge>
        </div>
      )}
      <div className="px-5 pb-2">
        <LineupTable team={team} />
      </div>
      {rows.length > 0 && series.length > 0 && (
        <div className="border-t border-[var(--hairline)] p-5">
          <div className="dz-eyebrow mb-2">Starter scoring breakdown</div>
          <StackedBreakdown
            data={rows}
            series={series}
            xKey="player"
            xLabel="Player"
            title={`${team.team_name ?? "Team"} scoring breakdown`}
            height={200}
          />
        </div>
      )}
    </Card>
  );
}

export function BoxScorePage() {
  const { matchupId } = useParams();
  const id = Number(matchupId);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.boxScore(id),
    queryFn: () => fetchBoxScore(id),
    enabled: Number.isFinite(id),
  });

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">
            <Link to="/matchups" className="hover:text-accent">
              ← Matchups
            </Link>
            {data?.season_year ? ` · ${data.season_year} · week ${data.week}` : ""}
          </div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Box Score</h1>
        </div>
        {data?.is_playoff && <Badge variant="accent">playoff</Badge>}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      )}
      {isError && <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />}

      {data && !data.available && (
        <Card className="space-y-4 p-8">
          <DataGap reason={data.reason ?? undefined} />
          <p className="text-[var(--fs-sm)] text-muted">
            Team totals can still be reviewed from the weekly matchups view.
          </p>
          {data.week != null && (
            <Link to={`/matchups?week=${data.week}`} className="text-accent hover:underline">
              View week {data.week} matchups
            </Link>
          )}
        </Card>
      )}

      {data && data.available && data.home && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TeamColumn team={data.home} isWinner={data.winner_team_id === data.home.team_id} />
          {data.away && (
            <TeamColumn team={data.away} isWinner={data.winner_team_id === data.away.team_id} />
          )}
        </div>
      )}
    </div>
  );
}
