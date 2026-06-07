import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import {
  Card,
  CardHeader,
  Chip,
  DataGap,
  RecordLine,
  Skeleton,
  Stat,
  Trophy,
} from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";
import { deriveSeasonPhase } from "@/lib/seasonPhase";

async function fetchStandings(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/standings", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("standings");
  return data.data;
}

async function fetchRecords() {
  const { data, error } = await api.GET("/v1/records");
  if (error || !data) throw new Error("records");
  return data.data as Record<
    string,
    {
      available?: boolean;
      value?: number;
      owner_name?: string | null;
      player_name?: string | null;
      season_year?: number | null;
      reason?: string;
    }
  >;
}

async function fetchTopScorers(season: number, week?: number) {
  const { data, error } = await api.GET("/v1/stats/top-scorers", {
    params: { query: { season, week, limit: 5 } },
  });
  if (error || !data) throw new Error("top scorers");
  return data.data;
}

export function HomePage() {
  const { current, seasons } = useSeasons();
  const phase = deriveSeasonPhase({ current, seasons });
  const seasonId = phase.lastCompletedSeason?.season_id ?? current?.season_id;
  const scorerSeason = phase.lastCompletedSeason?.season_year ?? current?.season_year;
  const standings = useQuery({
    queryKey: seasonId ? qk.standings(seasonId) : ["standings", "none"],
    queryFn: () => fetchStandings(seasonId as number),
    enabled: seasonId != null,
  });
  const records = useQuery({ queryKey: qk.records, queryFn: fetchRecords });
  const scorers = useQuery({
    queryKey: scorerSeason
      ? qk.topScorers({ season: scorerSeason, limit: 5 })
      : ["scorers", "none"],
    queryFn: () => fetchTopScorers(scorerSeason as number),
    enabled: scorerSeason != null,
  });

  const leader = standings.data?.rows[0];
  const champion = phase.lastCompletedSeason?.champion ?? current?.champion;

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Command center</div>
        <h1 className="font-display text-[var(--fs-display)] font-bold leading-none tracking-wide">
          The Danger Zone
        </h1>
        <p className="mt-2 max-w-xl text-[var(--fs-sm)] text-muted">
          Season-aware league context from backend metrics. Gaps are shown honestly, never faked.
        </p>
      </div>

      <Card className="p-5">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
          <Stat label="Seasons" value={seasons.length} />
          <Stat
            label={`${standings.data?.season_year ?? current?.season_year ?? ""} leader`}
            value={leader ? <Chip name={leader.owner_name} /> : "—"}
            tone="accent"
          />
          <Stat
            label={`${phase.lastCompletedSeason?.season_year ?? ""} champion`}
            value={champion?.owner_name ?? "—"}
            tone="win"
          />
          <Stat label="Phase" value={phase.phase === "offseason" ? "Off-season" : "In season"} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader eyebrow="last completed season" title="Champion" />
          <div className="p-5">
            {champion ? (
              <div className="flex items-center gap-3">
                <Trophy label="Champion" />
                <Chip name={champion.owner_name ?? champion.team_name} />
              </div>
            ) : (
              <DataGap reason="bracket_unavailable" />
            )}
            <p className="mt-3 text-[var(--fs-xs)] text-faint">
              Playoff bracket structure is not inferred until the bracket endpoint is proven.
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader
            eyebrow={phase.phase === "offseason" ? "past season" : "this season"}
            title="Top scorers"
          />
          <div className="space-y-2 p-5">
            {scorers.isLoading && <Skeleton className="h-24 w-full" />}
            {scorers.data?.scorers.slice(0, 5).map((s, i) => (
              <Link
                key={`${s.player_id}-${s.week}`}
                to={`/players/${s.player_id}`}
                className="flex items-center justify-between hover:text-accent"
              >
                <span className="text-[var(--fs-sm)]">
                  <span className="num text-faint">{i + 1}. </span>
                  {s.name_full}
                </span>
                <span className="num text-accent">{num(s.points)}</span>
              </Link>
            ))}
            {scorers.data && scorers.data.scorers.length === 0 && (
              <DataGap reason="no_scored_data" />
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            eyebrow={`season ${current?.season_year ?? ""}`}
            title="Standings"
            action={
              <Link to="/standings" className="dz-badge dz-badge--accent">
                Full table →
              </Link>
            }
          />
          {standings.isLoading && (
            <div className="space-y-2 p-5">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}
          {standings.data && (
            <table className="dz-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Manager</th>
                  <th className="dz-num">Record</th>
                  <th className="dz-num">PF</th>
                </tr>
              </thead>
              <tbody>
                {standings.data.rows.map((r) => (
                  <tr key={r.team_id}>
                    <td className="num text-faint">{r.rank}</td>
                    <td>
                      <Chip name={r.owner_name} />
                    </td>
                    <td className="dz-num">
                      <RecordLine wins={r.wins} losses={r.losses} ties={r.ties} />
                    </td>
                    <td className="dz-num">{num(r.points_for)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card>
          <CardHeader
            eyebrow="all-time"
            title="Records"
            action={
              <Link to="/records" className="dz-badge dz-badge--accent">
                Records book →
              </Link>
            }
          />
          <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2">
            {[
              "highest_team_score",
              "lowest_team_score",
              "best_player_week",
              "most_championships",
              "biggest_blowout",
              "narrowest_win",
            ].map(
              (key) => {
                const rec = records.data?.[key];
                const ok = rec && rec.available !== false && rec.value !== undefined;
                return (
                  <div key={key} className="bg-[var(--surface-1)] p-4">
                    <div className="dz-eyebrow mb-1">{key.replace(/_/g, " ")}</div>
                    {records.isLoading ? (
                      <Skeleton className="h-7 w-24" />
                    ) : ok ? (
                      <>
                        <div className="num text-[var(--fs-h1)] font-semibold text-accent">
                          {num(rec.value, Number.isInteger(rec.value) ? 0 : 2)}
                        </div>
                        <div className="text-[var(--fs-xs)] text-faint">
                          {rec.player_name ?? rec.owner_name ?? "—"}
                          {rec.season_year ? ` · ${rec.season_year}` : ""}
                        </div>
                      </>
                    ) : (
                      <DataGap reason={rec?.reason} />
                    )}
                  </div>
                );
              },
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
