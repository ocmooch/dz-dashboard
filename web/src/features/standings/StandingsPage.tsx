import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { RankFlow } from "@/charts";
import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, RecordLine, Skeleton, Tabs, Trophy, WeekStepper } from "@/design-system";
import { PowerTable } from "@/features/power/PowerTable";
import { usePower, usePowerTimeline } from "@/features/power/usePower";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { num, ordinal, pct, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";
import { toRankFlow } from "@/lib/rankflow";

type Lens = "record" | "power";

type ConferenceSection = components["schemas"]["ConferenceSection"];
type StandingsInsightTeam = components["schemas"]["StandingsInsightTeam"];

async function fetchConferences(seasonId: number, week?: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/conferences", {
    params: { path: { season_id: seasonId }, query: { through_week: week } },
  });
  if (error || !data) throw new Error("Failed to load conferences");
  return data.data;
}

async function fetchStandings(seasonId: number, week?: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/standings", {
    params: { path: { season_id: seasonId }, query: { through_week: week } },
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

async function fetchInsights(seasonId: number, week?: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/standings/insights", {
    params: { path: { season_id: seasonId }, query: { through_week: week } },
  });
  if (error || !data) throw new Error("Failed to load standings insights");
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

function LuckCallout({ kind, team }: { kind: "robbed" | "blessed"; team: StandingsInsightTeam }) {
  const robbed = kind === "robbed";
  const gap = Math.abs(team.luck_delta);
  const wins = gap === 1 ? "win" : "wins";
  return (
    <Link to={`/managers/${team.owner_id}`} className="block bg-[var(--surface-2)] p-4 transition-colors hover:bg-[var(--surface-3)]">
      <div className={`dz-eyebrow mb-1 ${robbed ? "text-loss" : "text-win"}`}>{robbed ? "Robbed" : "Blessed"}</div>
      <div className="font-display text-[var(--fs-h3)] font-bold tracking-wide">{team.team_name ?? team.owner_name}</div>
      <p className="mt-1 text-[var(--fs-sm)] text-muted">
        Won {num(team.actual_wins, 2)}, {robbed ? "should have won" : "on just"} {num(team.expected_wins, 2)} —{" "}
        {robbed ? (
          <>the schedule cost them <span className="num text-loss">{num(gap, 2)}</span> {wins}.</>
        ) : (
          <>the schedule gifted them <span className="num text-win">{num(gap, 2)}</span> {wins}.</>
        )}
      </p>
    </Link>
  );
}

function DivisionTable({ conf, showFinalPlacement }: { conf: ConferenceSection; showFinalPlacement: boolean }) {
  const title = conf.name ?? `Division ${conf.division_number}`;
  return (
    <Card>
      <CardHeader eyebrow="regular season division" title={title} />
      <div className="overflow-x-auto">
        <table className="dz-table w-full">
          <thead>
            <tr>
              <th>#</th>
              <th className="dz-num">OVR</th>
              <th>Team</th>
              <th className="dz-num">Record</th>
              <th className="dz-num">Win%</th>
              <th className="dz-num">PF</th>
              <th className="dz-num">PA</th>
              <th className="dz-num">DIV</th>
              {showFinalPlacement && <th className="dz-num">Finish</th>}
              <th className="dz-num">Streak</th>
            </tr>
          </thead>
          <tbody>
            {conf.teams.map((t) => (
              <tr key={t.team_id}>
                <td className="num text-faint">{t.conference_rank}</td>
                <td className="dz-num text-faint">{t.overall_rank}</td>
                <td>
                  <Link to={`/teams/${t.team_id}`} className="hover:text-accent">
                    <Chip name={t.team_name ?? t.owner_name} sub={t.owner_name ?? undefined} avatarUrl={teamAvatarUrl(t.team_id)} />
                  </Link>
                </td>
                <td className="dz-num">
                  <RecordLine wins={t.wins} losses={t.losses} ties={t.ties} />
                </td>
                <td className="dz-num text-muted">{pct(t.win_pct)}</td>
                <td className="dz-num">{num(t.points_for)}</td>
                <td className="dz-num text-muted">{num(t.points_against)}</td>
                <td className="dz-num text-muted">
                  <RecordLine wins={t.division_wins} losses={t.division_losses} ties={t.division_ties} />
                </td>
                {showFinalPlacement && (
                  <td className="dz-num"><PlacementCell finalRank={t.final_rank} /></td>
                )}
                <td className="dz-num"><StreakCell streak={t.streak} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function StandingsPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const [params, setParams] = useSearchParams();
  const lens: Lens = params.get("lens") === "power" ? "power" : "record";
  const weekParam = params.get("week");
  const week = weekParam ? Math.max(1, Number(weekParam) || 1) : undefined;
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: seasonId ? qk.standings(seasonId, week) : ["standings", "none"],
    queryFn: () => fetchStandings(seasonId as number, week),
    enabled: seasonId != null && lens === "record",
  });
  const timeline = useQuery({
    queryKey: seasonId ? qk.standingsTimeline(seasonId) : ["standings", "none", "timeline"],
    queryFn: () => fetchTimeline(seasonId as number),
    enabled: seasonId != null,
  });
  const insights = useQuery({
    queryKey: seasonId ? qk.standingsInsights(seasonId, week) : ["standings", "none", "insights"],
    queryFn: () => fetchInsights(seasonId as number, week),
    enabled: seasonId != null && lens === "record",
  });
  const conferences = useQuery({
    queryKey: seasonId ? qk.conferences(seasonId, week) : ["conferences", "none"],
    queryFn: () => fetchConferences(seasonId as number, week),
    enabled: seasonId != null && lens === "record",
  });

  const power = usePower(seasonId, week, lens === "power");
  const powerTimeline = usePowerTimeline(seasonId, lens === "power");
  const regWeeks = data?.regular_season_weeks;
  const powerRegWeeks = power.data?.regular_season_weeks;
  const effectiveWeek = week ?? regWeeks ?? powerRegWeeks;

  function setLens(next: Lens) {
    const p = new URLSearchParams(params);
    if (next === "power") p.set("lens", "power");
    else p.delete("lens");
    setParams(p, { replace: true });
  }
  function setWeek(w: number) {
    const p = new URLSearchParams(params);
    p.set("week", String(w));
    setParams(p, { replace: true });
  }

  const flow = timeline.data ? toRankFlow(timeline.data.teams) : null;
  const powerFlow = powerTimeline.data ? toRankFlow(powerTimeline.data.teams) : null;
  const showFinalPlacement =
    data != null &&
    data.through_week === data.regular_season_weeks &&
    data.rows.some((row) => row.final_rank != null);
  const historical = current != null && current.season_year >= 2010 && current.season_year <= 2019;
  const historicalCompleted =
    historical &&
    conferences.data?.available === true &&
    conferences.data.through_week === conferences.data.regular_season_weeks;

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Standings</h1>
        </div>
        <div className="flex items-center gap-3">
          <Tabs<Lens>
            tabs={[
              { id: "record", label: "Record" },
              { id: "power", label: "Power" },
            ]}
            value={lens}
            onChange={setLens}
          />
          {lens === "record" && data && (
            <Badge variant={historicalCompleted || data.rank_basis === "final_rank" ? "default" : "accent"}>
              order: {historicalCompleted || data.rank_basis === "final_rank" ? "official (NFL.com)" : "computed · wins→PF"}
            </Badge>
          )}
          {lens === "power" && power.data && (
            <Badge variant="accent">through week {power.data.through_week}</Badge>
          )}
        </div>
      </div>

      {lens === "record" && data?.tiebreak_caveat && !historicalCompleted && (
        <Badge variant="gap">historical tiebreak may differ from NFL.com for this era</Badge>
      )}

      {lens === "record" && (
        <>
      {!historical && <Card>
        <CardHeader
          eyebrow="regular season"
          title="Table"
          action={regWeeks ? <WeekStepper week={effectiveWeek ?? regWeeks} min={1} max={regWeeks} onChange={setWeek} /> : undefined}
        />
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
                  <th>Team</th>
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
                        <Chip name={r.team_name ?? r.owner_name} sub={r.owner_name ?? undefined} avatarUrl={teamAvatarUrl(r.team_id)} />
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
      </Card>}

      {historical && (
        <>
          <div className="flex items-center justify-between">
            <div className="dz-eyebrow">regular season divisions</div>
            {regWeeks && <WeekStepper week={effectiveWeek ?? regWeeks} min={1} max={regWeeks} onChange={setWeek} />}
          </div>
          {isLoading && <Card><div className="space-y-2 p-5">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div></Card>}
          {isError && <Card><ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} /></Card>}
          {conferences.data?.available && conferences.data.conferences.map((conf) => (
            <DivisionTable key={conf.conference_id} conf={conf} showFinalPlacement={showFinalPlacement} />
          ))}
          {conferences.data && !conferences.data.available && conferences.data.reason !== "no_conferences_this_season" && (
            <Card><div className="p-5"><DataGap reason={conferences.data.reason ?? "historical_division_mapping_gap"} /></div></Card>
          )}
        </>
      )}

      <Card>
        <CardHeader eyebrow="all-play expected wins vs actual" title="Robbed &amp; Blessed" />
        {insights.isLoading && <Skeleton className="m-5 h-28 w-[calc(100%-2.5rem)]" />}
        {insights.data && !insights.data.available && (
          <div className="p-5">
            <DataGap reason={insights.data.reason ?? "no_standings_rows"} />
          </div>
        )}
        {insights.data?.available && (
          <>
            {(insights.data.most_robbed || insights.data.most_blessed) && (
              <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2">
                {insights.data.most_robbed && <LuckCallout kind="robbed" team={insights.data.most_robbed} />}
                {insights.data.most_blessed && <LuckCallout kind="blessed" team={insights.data.most_blessed} />}
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="dz-table">
                <thead>
                  <tr>
                    <th>Manager</th>
                    <th className="dz-num">Actual W</th>
                    <th className="dz-num">Expected W</th>
                    <th className="dz-num">Luck</th>
                    <th className="dz-num">PF rank</th>
                  </tr>
                </thead>
                <tbody>
                  {insights.data.teams.map((r) => (
                    <tr key={r.team_id}>
                      <td>
                        <Link to={`/managers/${r.owner_id}`} className="hover:text-accent">
                          <Chip name={r.team_name ?? r.owner_name} sub={r.owner_name ?? undefined} avatarUrl={teamAvatarUrl(r.team_id)} />
                        </Link>
                      </td>
                      <td className="dz-num">{num(r.actual_wins, 2)}</td>
                      <td className="dz-num text-muted">{num(r.expected_wins, 2)}</td>
                      <td className={`dz-num ${r.luck_delta >= 0 ? "text-win" : "text-loss"}`}>
                        {r.luck_delta > 0 ? "+" : ""}
                        {num(r.luck_delta, 2)}
                      </td>
                      <td className="dz-num text-muted">#{r.points_for_rank}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
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
        </>
      )}

      {lens === "power" && (
        <>
          <Card>
            <CardHeader
              eyebrow="model · all-play adjusted · re-sorted by strength"
              title="Power, as of the selected week"
              action={
                powerRegWeeks ? (
                  <WeekStepper week={effectiveWeek ?? powerRegWeeks} min={1} max={powerRegWeeks} onChange={setWeek} />
                ) : undefined
              }
            />
            {power.isLoading && (
              <div className="space-y-2 p-5">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            )}
            {power.isError && (
              <ErrorState message="Could not reach the analytics service." onRetry={() => power.refetch()} />
            )}
            {power.data && (power.data.rows.length > 0 ? (
              <PowerTable data={power.data} />
            ) : (
              <div className="p-5">
                <DataGap reason="no_standings_rows" />
              </div>
            ))}
          </Card>

          <Card>
            <CardHeader eyebrow="rank by week" title="Power over time" />
            <div className="p-5">
              {powerTimeline.isLoading && <Skeleton className="h-[280px] w-full" />}
              {powerFlow && powerFlow.data.length > 0 ? (
                <RankFlow
                  title="Power ranking by week (rank 1 on top)"
                  data={powerFlow.data}
                  series={powerFlow.series}
                  xKey="week"
                  xLabel="Week"
                  teamCount={powerFlow.teamCount}
                  height={300}
                />
              ) : (
                !powerTimeline.isLoading && (
                  <p className="text-[var(--fs-sm)] text-faint">No weekly data for this season yet.</p>
                )
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
