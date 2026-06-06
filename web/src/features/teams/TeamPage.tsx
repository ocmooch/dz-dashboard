import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { LineTrend } from "@/charts";
import {
  Badge,
  Card,
  CardHeader,
  Chip,
  DataGap,
  EmptyState,
  ErrorState,
  UNSCORED_SEASON_NOTE,
  Pill,
  RecordLine,
  Skeleton,
  Stat,
  Trophy,
  WeekStepper,
} from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

async function fetchOverview(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load team");
  return data.data;
}

async function fetchRoster(id: number, week: number | null) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/roster", {
    params: { path: { team_id: id }, query: { week: week ?? undefined } },
  });
  if (error || !data) throw new Error("Failed to load roster");
  return data.data;
}

async function fetchSchedule(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/schedule", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load schedule");
  return data.data;
}

async function fetchScoringTrend(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/scoring-trend", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load scoring trend");
  return data.data;
}

async function fetchTransactions(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/transactions", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load transactions");
  return data.data;
}

function RosterCard({ teamId }: { teamId: number }) {
  const [params, setParams] = useSearchParams();
  const weekParam = params.get("week");
  const week = weekParam == null ? null : Math.max(1, Number(weekParam) || 1);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.teamRoster(teamId, week),
    queryFn: () => fetchRoster(teamId, week),
  });

  const weeks = data?.weeks_available ?? [];
  const minWeek = weeks[0] ?? 1;
  const maxWeek = weeks[weeks.length - 1] ?? 1;
  const activeWeek = data?.week ?? week ?? maxWeek;

  const setWeek = (w: number) => {
    const next = new URLSearchParams(params);
    next.set("week", String(w));
    setParams(next, { replace: true });
  };

  return (
    <Card>
      <CardHeader
        eyebrow={`week ${activeWeek}`}
        title="Roster"
        action={
          weeks.length > 1 ? (
            <WeekStepper week={activeWeek} min={minWeek} max={maxWeek} onChange={setWeek} />
          ) : undefined
        }
      />
      {isLoading && (
        <div className="space-y-2 p-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      )}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}
      {data && data.players.length === 0 && (
        <EmptyState title="No roster recorded" hint="No roster snapshot for this week." />
      )}
      {data && data.players.length > 0 && (
        <div className="overflow-x-auto">
          <table className="dz-table">
            <thead>
              <tr>
                <th>Slot</th>
                <th>Player</th>
                <th>Pos</th>
                <th className="dz-num">Points</th>
              </tr>
            </thead>
            <tbody>
              {data.players.map((p) => (
                <tr key={p.player_id} className={p.is_starter ? "" : "opacity-70"}>
                  <td className="font-mono text-[var(--fs-xs)] text-muted">
                    {p.roster_slot ?? "—"}
                  </td>
                  <td>
                    <Link to={`/players/${p.player_id}`} className="hover:text-accent">
                      <Chip name={p.player_name} sub={p.nfl_team ?? undefined} />
                    </Link>
                  </td>
                  <td className="text-muted">{p.position ?? "—"}</td>
                  <td className="dz-num">
                    {p.league_points == null ? (
                      <DataGap reason={data.is_scored ? "no_scored_data" : "season_unscored"} size="sm" />
                    ) : (
                      num(p.league_points)
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function ScheduleCard({ teamId }: { teamId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.teamSchedule(teamId),
    queryFn: () => fetchSchedule(teamId),
  });
  return (
    <Card>
      <CardHeader eyebrow="results" title="Schedule" />
      {isLoading && <Skeleton className="m-5 h-40" />}
      {data && data.games.length === 0 && <EmptyState title="No games scheduled" />}
      {data && data.games.length > 0 && (
        <ol className="divide-y divide-[var(--hairline)]">
          {data.games.map((g) => {
            const tone =
              g.result === "W" ? "text-win" : g.result === "L" ? "text-loss" : "text-muted";
            return (
              <li key={g.matchup_id} className="flex items-center justify-between gap-3 px-5 py-3">
                <div className="flex items-center gap-3">
                  <span className={`num w-6 font-bold ${tone}`}>{g.result ?? "—"}</span>
                  <div>
                    <Link to={`/matchups/${g.matchup_id}`} className="text-text hover:text-accent">
                      vs {g.opponent_owner_name ?? g.opponent_team_name ?? "Bye"}
                    </Link>
                    <div className="text-[var(--fs-xs)] text-faint">
                      wk {g.week}
                      {g.is_playoff ? " · playoff" : ""}
                    </div>
                  </div>
                </div>
                <span className="num text-[var(--fs-sm)]">
                  <span className={tone}>{num(g.team_score)}</span>
                  <span className="text-faint"> – </span>
                  <span className="text-muted">{num(g.opponent_score)}</span>
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}

function ScoringTrendCard({ teamId }: { teamId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.teamScoringTrend(teamId),
    queryFn: () => fetchScoringTrend(teamId),
  });
  return (
    <Card>
      <CardHeader eyebrow="vs league average" title="Scoring Trend" />
      <div className="p-5">
        {isLoading && <Skeleton className="h-48 w-full" />}
        {data && data.points.length === 0 && <EmptyState title="No scores yet" />}
        {data && data.points.length > 0 && (
          <LineTrend
            title="Team score vs league average by week"
            data={data.points.map((p) => ({
              week: `Wk ${p.week}`,
              team: p.team_score ?? null,
              league: p.league_avg ?? null,
            }))}
            xKey="week"
            xLabel="Week"
            series={[
              { key: "team", label: "This team" },
              { key: "league", label: "League avg" },
            ]}
            height={240}
          />
        )}
      </div>
    </Card>
  );
}

function TransactionsCard({ teamId }: { teamId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.teamTransactions(teamId),
    queryFn: () => fetchTransactions(teamId),
  });
  return (
    <Card>
      <CardHeader eyebrow="moves" title="Transactions" />
      {isLoading && <Skeleton className="m-5 h-32" />}
      {data && data.transactions.length === 0 && (
        <EmptyState title="No transactions" hint="No moves recorded for this team's season." />
      )}
      {data && data.transactions.length > 0 && (
        <ol className="divide-y divide-[var(--hairline)]">
          {data.transactions.map((t) => (
            <li key={t.transaction_id} className="flex items-center justify-between gap-3 px-5 py-3">
              <div>
                <span className="text-text">{t.player_name ?? "—"}</span>
                <div className="text-[var(--fs-xs)] text-faint">
                  {t.effective_week != null ? `wk ${t.effective_week}` : ""}
                  {t.direction ? ` · ${t.direction}` : ""}
                </div>
              </div>
              <Pill>{t.transaction_type}</Pill>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

export function TeamPage() {
  const params = useParams();
  const teamId = Number(params.teamId);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.team(teamId),
    queryFn: () => fetchOverview(teamId),
    enabled: Number.isFinite(teamId),
  });

  return (
    <div className="dz-rise space-y-4">
      <div>
        <div className="dz-eyebrow mb-1">
          {data ? `Season ${data.season_year}` : "Team"}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">
            {data?.team_name ?? "Team"}
          </h1>
          {data?.is_champion && <Trophy label="Champion" />}
          {data && (
            <Link to={`/managers/${data.owner_id}`} className="text-muted hover:text-accent">
              {data.owner_name ?? "—"}
            </Link>
          )}
        </div>
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data && (
        <>
          <Card className="p-5">
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
              <Stat
                label="Rank"
                value={data.rank ?? "—"}
                unit={data.rank_basis === "final_rank" ? "official" : "computed"}
                tone="accent"
              />
              <div>
                <div className="dz-eyebrow mb-1">Record</div>
                <div className="font-display text-[30px] font-bold leading-none tracking-wide">
                  <RecordLine wins={data.wins} losses={data.losses} ties={data.ties} />
                </div>
              </div>
              <Stat label="Points for" value={num(data.points_for, 1)} tone="win" />
              <Stat label="Points against" value={num(data.points_against, 1)} tone="loss" />
            </div>
            {!data.is_scored && (
              <div className="mt-4 border-t border-[var(--hairline)] pt-4">
                <Badge variant="gap">{UNSCORED_SEASON_NOTE}</Badge>
              </div>
            )}
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RosterCard teamId={teamId} />
            <ScheduleCard teamId={teamId} />
          </div>

          <ScoringTrendCard teamId={teamId} />
          <TransactionsCard teamId={teamId} />
        </>
      )}
    </div>
  );
}
