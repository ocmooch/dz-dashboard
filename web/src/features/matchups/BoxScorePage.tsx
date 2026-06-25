import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { StackedBreakdown, type ChartRow, type SeriesDef } from "@/charts";
import { InjuryBadge } from "@/components/InjuryBadge";
import { PlayerScoreCell } from "@/components/PlayerScoreCell";
import { Badge, BracketBadge, Card, CardHeader, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { MatchupFlags } from "@/features/matchups/MatchupFlags";
import { api } from "@/lib/api/client";
import { num, pct } from "@/lib/format";
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

/** Slot names the backend treats as injured-reserve / unavailable. Mirrors
 *  ``analytics/matchups.py::IR_SLOTS`` — kept in sync manually since the
 *  frontend cannot import backend constants. */
const IR_SLOT_NAMES = new Set(["IR", "IR2", "RES", "TAXI", "NA"]);

function isIR(slot: string | null | undefined): boolean {
  return !!slot && IR_SLOT_NAMES.has(slot.toUpperCase());
}

function contextTone(label: string | null | undefined): string {
  if (label === "DATA") return "border-[color:var(--loss)] text-loss";
  if (label === "INJ") return "border-[color:var(--warn)] text-[var(--warn)]";
  if (label === "RES") return "border-[color:var(--muted)] text-muted";
  if (label === HAMLIN_LABEL) return "border-[color:var(--accent)] text-accent";
  return "border-[color:var(--hairline)] text-faint";
}

function showRowContext(p: BoxPlayer): boolean {
  return !!p.context_label && !["Bye", "DNP", "Out", "Check"].includes(p.context_label);
}

const HAMLIN_LABEL = "Wk17+19";

/** Tooltip for a no-contest substitute: the context note plus the wk17-partial +
 *  Wild-Card (wk19) split that makes up the player's league points. */
function hamlinTitle(p: BoxPlayer): string | undefined {
  const sub = p.hamlin_substitute;
  if (!sub) return p.context_detail ?? undefined;
  const wk17 = sub.wk17_partial?.points;
  const wk19 = sub.wk19?.points;
  const split =
    wk17 != null && wk19 != null
      ? ` Week-17 partial ${num(wk17)} + Wild Card (Wk19) ${num(wk19)} = ${num(sub.league_points)}.`
      : "";
  return `${p.context_detail ?? ""}${split}`.trim() || undefined;
}

function ContextBadge({ p }: { p: BoxPlayer }) {
  if (!showRowContext(p)) return null;
  const isHamlin = !!p.hamlin_substitute;
  return (
    <span
      className={`ml-1 rounded border px-1 py-0.5 align-middle text-[10px] font-bold leading-none ${contextTone(p.context_label)}`}
      title={isHamlin ? hamlinTitle(p) : (p.context_detail ?? undefined)}
    >
      {p.context_label}
    </span>
  );
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
  const bench = team.lineup.filter((p) => !p.is_starter && !isIR(p.roster_slot));
  const ir = team.lineup.filter((p) => !p.is_starter && isIR(p.roster_slot));
  return (
    <table className="dz-table">
      <thead>
        <tr>
          <th>Slot</th>
          <th>Player</th>
          <th className="dz-num" title="Pre-game projected fantasy points">Proj</th>
          <th className="dz-num" title="Player's share of their team's total points scored">Share</th>
          <th className="dz-num" title="Actual vs projected (+/− delta).">Value</th>
          <th className="dz-num" title="Fantasy points scored. Context flags explain byes, DNPs, injury designations, and reserve-slot scores.">Pts</th>
        </tr>
      </thead>
      <tbody>
        {starters.map((p) => (
          <PlayerRow key={p.player_id} p={p} />
        ))}
        {bench.length > 0 && (
          <tr>
            <td colSpan={6} className="dz-eyebrow pt-3 text-faint">
              bench
            </td>
          </tr>
        )}
        {bench.map((p) => (
          <PlayerRow key={p.player_id} p={p} muted />
        ))}
        {ir.length > 0 && (
          <tr>
            <td colSpan={6} className="dz-eyebrow pt-3 text-faint">
              IR / RES
            </td>
          </tr>
        )}
        {ir.map((p) => (
          <PlayerRow key={p.player_id} p={p} muted />
        ))}
      </tbody>
    </table>
  );
}

function PlayerRow({ p, muted = false }: { p: BoxPlayer; muted?: boolean }) {
  return (
    <tr>
      <td className="num text-faint">{p.roster_slot ?? "—"}</td>
      <td className={muted ? "text-muted" : undefined}>
        {p.player_name ?? "—"}
        <span className="ml-1 text-[var(--fs-xs)] text-faint">{p.position}</span>
        {p.injury_status != null && (
          <InjuryBadge
            status={p.injury_status}
            bodyPart={p.injury_body_part}
            secondary={p.injury_secondary}
            practiceStatus={p.injury_practice_status}
          />
        )}
        <ContextBadge p={p} />
      </td>
      <td className="dz-num text-faint">
        {/* A missing projection is a plain dash; when the whole season lacks
            projection data the box score shows one top-level note instead of a
            gap chip on every row. */}
        {p.projection != null ? num(p.projection) : "—"}
      </td>
      <td className="dz-num text-faint">
        {p.team_point_share != null ? pct(p.team_point_share) : "—"}
      </td>
      <td className="dz-num">
        <span
          className={
            p.projection_delta == null
              ? "text-faint"
              : p.projection_delta >= 0
                ? "text-win"
                : "text-loss"
          }
          title={
            p.projection != null && p.league_points != null && p.projection_delta != null
              ? `Proj ${num(p.projection)} → Actual ${num(p.league_points)} (${p.projection_delta > 0 ? "+" : ""}${num(p.projection_delta)})`
              : undefined
          }
        >
          {p.projection_delta != null
            ? `${p.projection_delta > 0 ? "+" : ""}${num(p.projection_delta)}`
            : "—"}
        </span>
      </td>
      <td className="dz-num">
        {!p.available ? (
          // Pipeline explicitly flagged this entry as a gap (e.g. a known scoring hole).
          <DataGap reason={p.reason ?? undefined} size="sm" />
        ) : p.league_points != null ? (
          <PlayerScoreCell
            points={p.league_points}
            zeroReason={p.zero_reason}
            zeroDetail={p.zero_detail}
            zeroLabel={["Bye", "DNP", "Out"].includes(p.context_label ?? "") ? p.context_label : undefined}
            injuryBodyPart={p.injury_body_part}
            muted={muted}
          />
        ) : (
          <span className="text-faint">—</span>
        )}
      </td>
    </tr>
  );
}

function TeamColumn({
  team,
  isWinner,
  margin,
}: {
  team: BoxTeam;
  isWinner: boolean;
  margin: number | null | undefined;
}) {
  const starters = team.lineup.filter((p) => p.is_starter);
  const { rows, series } = breakdownChart(starters);
  // Signed margin beside the total, mirroring the weekly grid: winner +, loser −.
  const signedMargin = margin == null ? null : isWinner ? margin : -margin;
  return (
    <Card>
      <CardHeader
        eyebrow={team.owner_name ?? undefined}
        title={team.team_name ?? "—"}
        action={
          <span className="flex flex-col items-end">
            <span className={`num text-[var(--fs-h1)] font-bold ${isWinner ? "text-win" : "text-muted"}`}>
              {num(team.total_score)}
            </span>
            {signedMargin != null && (
              <span className={`num text-[var(--fs-xs)] ${signedMargin > 0 ? "text-win" : signedMargin < 0 ? "text-loss" : "text-muted"}`}>
                {signedMargin > 0 ? "+" : ""}
                {num(signedMargin)}
              </span>
            )}
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
      {team.roster_reconstructed && team.roster_reconstructed_note && (
        <div className="px-5 pb-2">
          <div
            className="rounded border border-[color:var(--hairline)] bg-[color:var(--surface-2)] px-3 py-2 text-[var(--fs-xs)] text-muted"
            role="note"
          >
            <span className="dz-eyebrow mr-1 text-faint">reconstructed</span>
            {team.roster_reconstructed_note}
          </div>
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
        {data?.bracket_tier ? (
          <BracketBadge tier={data.bracket_tier} />
        ) : (
          data?.is_playoff && <Badge variant="accent">playoff</Badge>
        )}
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

      {data && data.available && data.projections_available === false && (
        <div
          className="rounded border border-[color:var(--hairline)] bg-[color:var(--surface-2)] px-3 py-2 text-[var(--fs-xs)] text-muted"
          role="note"
        >
          <span className="dz-eyebrow mr-1 text-faint">note</span>
          Projection data isn’t available for the {data.season_year} season, so the Proj and Value
          columns are blank. Scoring is unaffected.
        </div>
      )}

      {data && data.available && data.resolution_note && (
        <div
          className="rounded border border-[color:var(--accent)] bg-[color:var(--surface-2)] px-4 py-3 text-[var(--fs-sm)] text-muted"
          role="note"
        >
          <span className="dz-eyebrow mr-1 text-accent">no-contest resolution</span>
          {data.resolution_note}
        </div>
      )}

      {data && data.available && data.flags && data.flags.length > 0 && (
        <MatchupFlags flags={data.flags} />
      )}

      {data && data.available && data.home && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TeamColumn
            team={data.home}
            isWinner={data.winner_team_id === data.home.team_id}
            margin={data.margin}
          />
          {data.away && (
            <TeamColumn
              team={data.away}
              isWinner={data.winner_team_id === data.away.team_id}
              margin={data.margin}
            />
          )}
        </div>
      )}
    </div>
  );
}
