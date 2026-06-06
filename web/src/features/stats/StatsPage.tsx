import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Card, CardHeader, Chip, EmptyState, ErrorState, UNSCORED_SEASON_NOTE, Skeleton, Tabs } from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

const POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"] as const;
type View = "top-scorers" | "season-totals";

async function fetchTopScorers(season: number, position: string, week: number | null) {
  const { data, error } = await api.GET("/v1/stats/top-scorers", {
    params: {
      query: {
        season,
        position: position || undefined,
        week: week ?? undefined,
        limit: 50,
      },
    },
  });
  if (error || !data) throw new Error("Failed to load top scorers");
  return data.data;
}

async function fetchSeasonTotals(season: number, position: string) {
  const { data, error } = await api.GET("/v1/stats/season-totals", {
    params: { query: { season, position: position || undefined } },
  });
  if (error || !data) throw new Error("Failed to load season totals");
  return data.data;
}

function PlayerCell({ id, name, sub }: { id: number; name: string; sub?: string }) {
  return (
    <Link to={`/players/${id}`} className="hover:text-accent">
      <Chip name={name} sub={sub} />
    </Link>
  );
}

export function StatsPage() {
  const { current } = useSeasons();
  const season = current?.season_year;
  const [view, setView] = useState<View>("top-scorers");
  const [position, setPosition] = useState("");
  const [week, setWeek] = useState<number | null>(null);

  const topScorers = useQuery({
    queryKey: qk.topScorers({ season, position, week }),
    queryFn: () => fetchTopScorers(season as number, position, week),
    enabled: season != null && view === "top-scorers",
  });
  const seasonTotals = useQuery({
    queryKey: qk.seasonTotals({ season, position }),
    queryFn: () => fetchSeasonTotals(season as number, position),
    enabled: season != null && view === "season-totals",
  });

  const active = view === "top-scorers" ? topScorers : seasonTotals;

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Season {season ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Stats Explorer</h1>
        </div>
        <Tabs
          tabs={[
            { id: "top-scorers", label: "Top scorers" },
            { id: "season-totals", label: "Season totals" },
          ]}
          value={view}
          onChange={setView}
        />
      </div>

      {current && !current.is_scored && (
        <Badge variant="gap">{UNSCORED_SEASON_NOTE}</Badge>
      )}

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <select
            className="dz-select"
            aria-label="Filter by position"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          >
            <option value="">All positions</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          {view === "top-scorers" && (
            <select
              className="dz-select"
              aria-label="Filter by week"
              value={week ?? ""}
              onChange={(e) => setWeek(e.target.value === "" ? null : Number(e.target.value))}
            >
              <option value="">Full season</option>
              {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
                <option key={w} value={w}>
                  Week {w}
                </option>
              ))}
            </select>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          eyebrow={view === "top-scorers" ? "best performances" : "cumulative"}
          title={view === "top-scorers" ? "Top Scorers" : "Season Totals"}
        />
        {active.isLoading && (
          <div className="space-y-2 p-5">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        )}
        {active.isError && (
          <ErrorState
            message="Could not reach the analytics service."
            onRetry={() => active.refetch()}
          />
        )}

        {view === "top-scorers" && topScorers.data && (
          topScorers.data.scorers.length === 0 ? (
            <EmptyState title="No scores" hint="No scored data for this scope." />
          ) : (
            <div className="overflow-x-auto">
              <table className="dz-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Player</th>
                    <th>Pos</th>
                    {week == null ? null : <th className="dz-num">Wk</th>}
                    <th className="dz-num">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {topScorers.data.scorers.map((s, i) => (
                    <tr key={`${s.player_id}-${s.week ?? "s"}`}>
                      <td className="num text-faint">{i + 1}</td>
                      <td>
                        <PlayerCell id={s.player_id} name={s.name_full} sub={s.nfl_team ?? undefined} />
                      </td>
                      <td className="text-muted">{s.position ?? "—"}</td>
                      {week == null ? null : <td className="dz-num text-muted">{s.week ?? "—"}</td>}
                      <td className="dz-num">{num(s.points)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {view === "season-totals" && seasonTotals.data && (
          seasonTotals.data.totals.length === 0 ? (
            <EmptyState title="No totals" hint="No scored data for this scope." />
          ) : (
            <div className="overflow-x-auto">
              <table className="dz-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Player</th>
                    <th>Pos</th>
                    <th className="dz-num">Weeks</th>
                    <th className="dz-num">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {seasonTotals.data.totals.map((t, i) => (
                    <tr key={t.player_id}>
                      <td className="num text-faint">{i + 1}</td>
                      <td>
                        <PlayerCell id={t.player_id} name={t.name_full} sub={t.nfl_team ?? undefined} />
                      </td>
                      <td className="text-muted">{t.position ?? "—"}</td>
                      <td className="dz-num text-muted">{t.weeks_played}</td>
                      <td className="dz-num">{num(t.total_points)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </Card>
    </div>
  );
}
