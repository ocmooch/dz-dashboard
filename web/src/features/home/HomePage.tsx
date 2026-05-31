import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Card, CardHeader, Chip, DataGap, RecordLine, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

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
  return data.data as Record<string, { available?: boolean; value?: number; owner_name?: string | null; player_name?: string | null; season_year?: number | null; reason?: string }>;
}

async function fetchPower(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/power", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("power");
  return data.data;
}

/** Movement of the model's rank vs the standings rank. >0 = riser, <0 = faller. */
function DeltaTag({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-faint">even</span>;
  const tone = delta > 0 ? "win" : "loss";
  return (
    <Badge variant={tone}>
      {delta > 0 ? `▲ ${delta}` : `▼ ${Math.abs(delta)}`}
    </Badge>
  );
}

export function HomePage() {
  const { current, seasons } = useSeasons();
  const seasonId = current?.season_id;
  const standings = useQuery({
    queryKey: seasonId ? qk.standings(seasonId) : ["standings", "none"],
    queryFn: () => fetchStandings(seasonId as number),
    enabled: seasonId != null,
  });
  const records = useQuery({ queryKey: qk.records, queryFn: fetchRecords });
  const power = useQuery({
    queryKey: seasonId ? qk.power(seasonId) : ["power", "none"],
    queryFn: () => fetchPower(seasonId as number),
    enabled: seasonId != null,
  });

  const leader = standings.data?.rows[0];
  const scoredCount = seasons.filter((s) => s.is_scored).length;
  // Top movers = the teams the model rates furthest from their record (the
  // biggest |rank_delta|); deep-link to the full power page. rank_delta is
  // already computed by the BFF — we only pick the largest swings to surface.
  const movers = [...(power.data?.rows ?? [])]
    .filter((r) => r.rank_delta !== 0)
    .sort((a, b) => Math.abs(b.rank_delta) - Math.abs(a.rank_delta))
    .slice(0, 4);

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Command center</div>
        <h1 className="font-display text-[var(--fs-display)] font-bold leading-none tracking-wide">
          The Danger Zone
        </h1>
        <p className="mt-2 max-w-xl text-[var(--fs-sm)] text-muted">
          {seasons.length} seasons of league history · {scoredCount} fully scored. Every number is
          computed server-side and read-only — gaps are shown honestly, never faked.
        </p>
      </div>

      <Card className="p-5">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
          <Stat label="Seasons" value={seasons.length} />
          <Stat label="Scored era" value={scoredCount} unit="yrs" />
          <Stat
            label={`${current?.season_year ?? ""} leader`}
            value={leader ? <Chip name={leader.owner_name} /> : "—"}
            tone="accent"
          />
          <Stat
            label={`${current?.season_year ?? ""} champion`}
            value={current?.champion?.owner_name ?? "—"}
            tone="win"
          />
        </div>
      </Card>

      <Card>
        <CardHeader
          eyebrow="power model · scoring over luck"
          title="Top movers"
          action={
            <Link to="/power" className="dz-badge dz-badge--accent">
              Power ranking →
            </Link>
          }
        />
        {power.isLoading ? (
          <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-[var(--surface-1)] p-4">
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
        ) : movers.length > 0 ? (
          <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
            {movers.map((r) => (
              <div key={r.team_id} className="flex items-center justify-between gap-2 bg-[var(--surface-1)] p-4">
                <Chip name={r.owner_name} sub={`power #${r.rank}`} />
                <DeltaTag delta={r.rank_delta} />
              </div>
            ))}
          </div>
        ) : (
          <p className="p-5 text-[var(--fs-sm)] text-faint">
            The model and the standings agree this week — no notable risers or fallers.
          </p>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
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
                {standings.data.rows.slice(0, 5).map((r) => (
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
            {["highest_team_score", "best_player_week", "most_championships", "biggest_blowout"].map(
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
