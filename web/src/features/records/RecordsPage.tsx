import { useQuery } from "@tanstack/react-query";

import { Badge, Card, DataGap, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

async function fetchRecords() {
  const { data, error } = await api.GET("/v1/records");
  if (error || !data) throw new Error("Failed to load records");
  return data.data as Record<string, RecordValue>;
}

type RecordValue = {
  available?: boolean;
  reason?: string;
  value?: number;
  owner_name?: string | null;
  team_name?: string | null;
  player_name?: string | null;
  season_year?: number | null;
  week?: number | null;
};

const RECORDS: { key: string; label: string; suffix?: string }[] = [
  { key: "highest_team_score", label: "Highest team score", suffix: " pts" },
  { key: "lowest_team_score", label: "Lowest team score", suffix: " pts" },
  { key: "biggest_blowout", label: "Biggest blowout", suffix: " margin" },
  { key: "narrowest_win", label: "Narrowest win", suffix: " margin" },
  { key: "highest_scoring_matchup", label: "Highest-scoring matchup", suffix: " total" },
  { key: "best_player_week", label: "Best player week", suffix: " pts" },
  { key: "most_championships", label: "Most championships", suffix: " 🏆" },
  { key: "best_season_points_for", label: "Best season (PF)", suffix: " pts" },
  { key: "longest_win_streak", label: "Longest win streak", suffix: " W" },
  { key: "longest_loss_streak", label: "Longest loss streak", suffix: " L" },
];

function who(rec: RecordValue): string {
  const parts: string[] = [];
  if (rec.player_name) parts.push(rec.player_name);
  if (rec.owner_name) parts.push(rec.owner_name);
  else if (rec.team_name) parts.push(rec.team_name);
  if (rec.season_year) parts.push(rec.week ? `${rec.season_year} · wk ${rec.week}` : `${rec.season_year}`);
  return parts.join(" — ") || "—";
}

function RecordCard({ label, suffix, rec }: { label: string; suffix?: string; rec?: RecordValue }) {
  const available = rec?.available !== false && rec?.value !== undefined;
  return (
    <Card hover className="p-5">
      <div className="dz-eyebrow mb-2">{label}</div>
      {available ? (
        <>
          <div className="num text-[var(--fs-display)] font-bold leading-none text-accent">
            {num(rec?.value, Number.isInteger(rec?.value) ? 0 : 2)}
            {suffix && <span className="text-[var(--fs-sm)] text-faint">{suffix}</span>}
          </div>
          <div className="mt-2 text-[var(--fs-sm)] text-muted">{who(rec as RecordValue)}</div>
        </>
      ) : (
        <DataGap reason={rec?.reason} />
      )}
    </Card>
  );
}

export function RecordsPage() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: qk.records, queryFn: fetchRecords });

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Hall of fame</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Records Book</h1>
        </div>
        {data?.scored_era && (
          <Badge>
            scored era {Array.isArray((data as Record<string, unknown>).scored_era)
              ? `${(data.scored_era as unknown as number[])[0]}–${(data.scored_era as unknown as number[]).slice(-1)[0]}`
              : ""}
          </Badge>
        )}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}
      {isError && <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />}
      {data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {RECORDS.map((r) => (
            <RecordCard key={r.key} label={r.label} suffix={r.suffix} rec={data[r.key]} />
          ))}
        </div>
      )}
    </div>
  );
}
