import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { BarCompare } from "@/charts";
import {
  Badge,
  Card,
  CardHeader,
  DataGap,
  EmptyState,
  ErrorState,
  Pill,
  Skeleton,
} from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

async function fetchPlayer(id: number) {
  const { data, error } = await api.GET("/v1/players/{player_id}", {
    params: { path: { player_id: id } },
  });
  if (error || !data) throw new Error("Failed to load player");
  return data.data;
}

async function fetchScoring(id: number, season: number) {
  const { data, error } = await api.GET("/v1/players/{player_id}/scoring", {
    params: { path: { player_id: id }, query: { season } },
  });
  if (error || !data) throw new Error("Failed to load scoring");
  return data.data;
}

async function fetchOwnership(id: number) {
  const { data, error } = await api.GET("/v1/players/{player_id}/ownership", {
    params: { path: { player_id: id } },
  });
  if (error || !data) throw new Error("Failed to load ownership");
  return data.data;
}

async function fetchAvailability(id: number, season: number) {
  const { data, error } = await api.GET("/v1/players/{player_id}/availability", {
    params: { path: { player_id: id }, query: { season } },
  });
  if (error || !data) throw new Error("Failed to load availability");
  return data.data;
}

const ID_LABELS: { key: string; label: string }[] = [
  { key: "nfl_com_player_id", label: "NFL.com" },
  { key: "gsis_id", label: "GSIS" },
  { key: "sleeper_id", label: "Sleeper" },
  { key: "espn_id", label: "ESPN" },
  { key: "yahoo_id", label: "Yahoo" },
];

function ScoringChart({ playerId, season }: { playerId: number; season: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.playerScoring(playerId, season),
    queryFn: () => fetchScoring(playerId, season),
  });
  if (isLoading) return <Skeleton className="h-48 w-full" />;
  if (!data) return null;
  if (!data.available) {
    return (
      <div className="p-5">
        <DataGap reason={data.reason ?? "no_scored_data"} />
      </div>
    );
  }
  if (data.weeks.length === 0) {
    return <EmptyState title="No scored weeks" hint="This player has no games this season." />;
  }
  const rows = data.weeks.map((w) => ({ week: `Wk ${w.week}`, points: w.points ?? null }));
  return (
    <div className="p-5">
      <BarCompare
        title={`Weekly league points — ${season}`}
        data={rows}
        xKey="week"
        xLabel="Week"
        series={[{ key: "points", label: "League points" }]}
        height={240}
      />
      <div className="mt-3 border-t border-[var(--hairline)] pt-3 text-[var(--fs-sm)] text-muted">
        Season total:{" "}
        <span className="num text-text">{num(data.total_points)}</span>
        {data.score_incomplete && (
          <span className="ml-2 text-[var(--fs-xs)] text-faint" title="Score may be understated — long TD bonus points (40+/50+ yd TDs) require play-by-play data not yet computed">
            *incomplete
          </span>
        )}
      </div>
      {data.score_incomplete && (
        <div className="mt-2">
          <DataGap reason="long_td_bonuses_not_computed" />
        </div>
      )}
    </div>
  );
}

function OwnershipTimeline({ playerId }: { playerId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.playerOwnership(playerId),
    queryFn: () => fetchOwnership(playerId),
  });
  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (!data) return null;
  if (data.events.length === 0) {
    return <EmptyState title="Never rostered" hint="No league team has owned this player." />;
  }
  return (
    <ol className="divide-y divide-[var(--hairline)]">
      {data.events.map((e, i) => (
        <li key={i} className="flex items-center justify-between gap-3 px-5 py-3">
          <div>
            <Link to={`/teams/${e.team_id}`} className="font-semibold text-text hover:text-accent">
              {e.team_name ?? `Team ${e.team_id}`}
            </Link>
            <div className="text-[var(--fs-xs)] text-faint">
              {e.season_year} · wk {e.week}
              {e.roster_slot ? ` · ${e.roster_slot}` : ""}
            </div>
          </div>
          {e.acquisition_type && <Pill>{e.acquisition_type}</Pill>}
        </li>
      ))}
    </ol>
  );
}

function AvailabilityStrip({ playerId, season }: { playerId: number; season: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.playerAvailability(playerId, season),
    queryFn: () => fetchAvailability(playerId, season),
  });
  if (isLoading) return <Skeleton className="h-16 w-full" />;
  if (!data) return null;
  if (!data.available) {
    return (
      <div className="p-5">
        <DataGap reason={data.reason ?? "availability_history_not_reconstructable"} />
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5 p-5">
      {data.weeks.map((w) => {
        const tone = w.status === "owned" ? "win" : "default";
        return (
          <Pill key={w.week} tone={tone}>
            wk{w.week} · {w.status}
          </Pill>
        );
      })}
    </div>
  );
}

export function PlayerDetailPage() {
  const params = useParams();
  const playerId = Number(params.playerId);
  const { current } = useSeasons();
  const season = current?.season_year;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.player(playerId),
    queryFn: () => fetchPlayer(playerId),
    enabled: Number.isFinite(playerId),
  });

  return (
    <div className="dz-rise space-y-4">
      <div>
        <Link to="/players" className="dz-eyebrow mb-1 inline-block hover:text-accent">
          ‹ Players
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">
            {data?.name_full ?? "Player"}
          </h1>
          {data?.position && <Badge variant="accent">{data.position}</Badge>}
          {data?.nfl_team && <Badge>{data.nfl_team}</Badge>}
          {data && (
            <Badge variant={data.is_active ? "win" : "default"}>
              {data.is_active ? "active" : "retired"}
            </Badge>
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
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <div className="dz-eyebrow mb-1">Rookie year</div>
                <div className="num text-text">{data.rookie_year ?? "—"}</div>
              </div>
              <div>
                <div className="dz-eyebrow mb-1">Born</div>
                <div className="num text-text">{data.birth_date ?? "—"}</div>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--hairline)] pt-4">
              {ID_LABELS.map(({ key, label }) => {
                const v = (data as Record<string, unknown>)[key];
                if (!v) return null;
                return (
                  <span key={key} className="font-mono text-[var(--fs-xs)] text-faint">
                    <span className="text-muted">{label}:</span> {String(v)}
                  </span>
                );
              })}
            </div>
          </Card>

          <Card>
            <CardHeader eyebrow={`season ${season ?? ""}`} title="Weekly Scoring" />
            {season != null ? (
              <ScoringChart playerId={playerId} season={season} />
            ) : (
              <EmptyState title="Pick a season" hint="Use the season switcher above." />
            )}
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader eyebrow="within the league" title="Ownership" />
              <OwnershipTimeline playerId={playerId} />
            </Card>
            <Card>
              <CardHeader eyebrow={`season ${season ?? ""}`} title="Availability" />
              {season != null ? (
                <AvailabilityStrip playerId={playerId} season={season} />
              ) : (
                <EmptyState title="Pick a season" />
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
