import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, Skeleton, Trophy } from "@/design-system";
import { api } from "@/lib/api/client";
import { num, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

async function fetchRecords() {
  const { data, error } = await api.GET("/v1/records");
  if (error || !data) throw new Error("Failed to load records");
  return data.data as Record<string, RecordValue>;
}

async function fetchChampionships() {
  const { data, error } = await api.GET("/v1/records/championships");
  if (error || !data) throw new Error("Failed to load championship history");
  return data.data;
}

type OwnerLite = { owner_id?: number; display_name?: string | null };
type RecordValue = {
  available?: boolean;
  reason?: string;
  value?: number;
  owner_name?: string | null;
  team_name?: string | null;
  player_name?: string | null;
  // matchup-scoped records carry both sides so the grid can name them.
  winner_name?: string | null;
  loser_name?: string | null;
  opponent_name?: string | null;
  season_year?: number | null;
  week?: number | null;
  // deep-link context — each record carries enough to reach its source.
  matchup_id?: number | null;
  player_id?: number | null;
  owner_id?: number | null;
  games_played?: number;
  owner_a?: OwnerLite;
  owner_b?: OwnerLite;
  score_gap?: boolean;
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
  if (rec.winner_name && rec.loser_name) parts.push(`${rec.winner_name} def. ${rec.loser_name}`);
  else if (rec.team_name && rec.opponent_name)
    parts.push(`${rec.team_name} vs ${rec.opponent_name}`);
  else if (rec.team_name) parts.push(rec.team_name);
  else if (rec.owner_name) parts.push(rec.owner_name);
  if (rec.season_year)
    parts.push(rec.week ? `${rec.season_year} · wk ${rec.week}` : `${rec.season_year}`);
  return parts.join(" — ") || "—";
}

/** Every record knows where it came from: a matchup, a player, an owner, or — for
 *  the closest rivalry — its pairwise page. Returns null when no target applies. */
function recordHref(key: string, rec: RecordValue): string | null {
  if (key === "closest_rivalry") {
    const a = rec.owner_a?.owner_id;
    const b = rec.owner_b?.owner_id;
    return a != null && b != null ? `/rivalries/${a}/vs/${b}` : null;
  }
  if (rec.matchup_id != null) return `/matchups/${rec.matchup_id}`;
  if (rec.player_id != null) return `/players/${rec.player_id}`;
  if (rec.owner_id != null) return `/managers/${rec.owner_id}`;
  return null;
}

function RecordBody({
  label,
  suffix,
  value,
  detail,
  available,
  reason,
  scoreGap,
}: {
  label: string;
  suffix?: string;
  value?: number;
  detail: string;
  available: boolean;
  reason?: string;
  scoreGap?: boolean;
}) {
  return (
    <Card hover className="h-full p-5">
      <div className="dz-eyebrow mb-2">{label}</div>
      {available ? (
        <>
          <div className="num text-[var(--fs-display)] font-bold leading-none text-accent">
            {num(value, Number.isInteger(value) ? 0 : 2)}
            {suffix && <span className="text-[var(--fs-sm)] text-faint">{suffix}</span>}
          </div>
          {scoreGap && (
            <div className="mt-1">
              <DataGap reason="long_td_bonuses_not_computed" size="sm" />
            </div>
          )}
          <div className="mt-2 text-[var(--fs-sm)] text-muted">{detail}</div>
        </>
      ) : (
        <DataGap reason={reason} />
      )}
    </Card>
  );
}

function RecordCard({
  recordKey,
  label,
  suffix,
  rec,
  value,
  detail,
}: {
  recordKey: string;
  label: string;
  suffix?: string;
  rec?: RecordValue;
  value?: number;
  detail?: string;
}) {
  const available = rec?.available !== false && (value ?? rec?.value) !== undefined;
  const href = rec && available ? recordHref(recordKey, rec) : null;
  const body = (
    <RecordBody
      label={label}
      suffix={suffix}
      value={value ?? rec?.value}
      detail={detail ?? who(rec ?? {})}
      available={available}
      reason={rec?.reason}
      scoreGap={rec?.score_gap}
    />
  );
  if (href) {
    return (
      <Link to={href} className="block focus:outline-none" aria-label={`${label} — view source`}>
        {body}
      </Link>
    );
  }
  return body;
}

function ChampionshipTimeline({ query }: { query: string }) {
  const { data, isLoading } = useQuery({ queryKey: qk.championships, queryFn: fetchChampionships });
  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!data) return null;
  const decided = data.seasons.filter((s) => s.champion);
  const filtered = decided.filter((s) => {
    const haystack = [
      s.season_year,
      s.champion?.owner_name,
      s.champion?.team_name,
      s.runner_up?.team_name,
      s.runner_up?.owner_name,
      s.last_place?.team_name,
      s.last_place?.owner_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {filtered.map((s) => {
        const teamId = s.champion?.team_id;
        const inner = (
          <>
            <div className="num text-[var(--fs-sm)] text-faint">{s.season_year}</div>
            <div className="mt-1 flex items-center gap-1.5">
              <Trophy />
              <Chip
                name={s.champion?.team_name ?? s.champion?.owner_name}
                sub={s.champion?.team_name && s.champion?.owner_name ? s.champion.owner_name : undefined}
                avatarUrl={teamId != null ? teamAvatarUrl(teamId) : undefined}
              />
            </div>
          </>
        );
        const cls = "dz-card dz-card--hover min-w-[140px] shrink-0 p-3";
        return teamId != null ? (
          <Link key={s.season_year} to={`/teams/${teamId}`} className={`${cls} block`}>
            {inner}
          </Link>
        ) : (
          <div key={s.season_year} className={cls}>
            {inner}
          </div>
        );
      })}
      {filtered.length === 0 && <DataGap reason="no_matching_records" />}
    </div>
  );
}

export function RecordsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.records,
    queryFn: fetchRecords,
  });

  const era = Array.isArray(data?.scored_era as unknown)
    ? (data!.scored_era as unknown as number[])
    : null;
  const rivalry = data?.closest_rivalry as RecordValue | undefined;
  const rivalryNames =
    rivalry?.owner_a?.display_name && rivalry?.owner_b?.display_name
      ? `${rivalry.owner_a.display_name} vs ${rivalry.owner_b.display_name}`
      : "—";
  const [trophyQuery, setTrophyQuery] = useState("");
  const visibleRecords = useMemo(
    () =>
      RECORDS.filter((r) =>
        r.label.toLowerCase().includes(trophyQuery.trim().toLowerCase()),
      ),
    [trophyQuery],
  );

  return (
    <div className="dz-rise space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Hall of fame</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Records Book</h1>
        </div>
        {era && era.length > 0 && (
          <Badge>
            scored era {era[0]}–{era[era.length - 1]}
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
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}
      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {visibleRecords.map((r) => (
              <RecordCard key={r.key} recordKey={r.key} label={r.label} suffix={r.suffix} rec={data[r.key]} />
            ))}
            <RecordCard
              recordKey="closest_rivalry"
              label="Closest rivalry"
              suffix=" games"
              rec={rivalry}
              value={rivalry?.games_played}
              detail={rivalryNames}
            />
          </div>

          <Card>
            <CardHeader eyebrow="league trophy case" title="Championship History" />
            <div className="p-5">
              <input
                className="dz-input mb-4 max-w-sm"
                value={trophyQuery}
                onChange={(e) => setTrophyQuery(e.target.value)}
                placeholder="Filter by manager, year, or record"
              />
              <ChampionshipTimeline query={trophyQuery} />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
