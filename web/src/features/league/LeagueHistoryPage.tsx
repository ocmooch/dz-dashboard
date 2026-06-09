import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { qk } from "@/lib/queryKeys";

type LeagueTimeline = components["schemas"]["LeagueTimeline"];
type LeagueChangeDetail = components["schemas"]["LeagueChangeDetail"];

async function fetchTimeline(): Promise<LeagueTimeline> {
  const { data, error } = await api.GET("/v1/league/timeline");
  if (error || !data) throw new Error("league timeline");
  return data.data;
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    nfl_com_authoritative_total: "NFL.com team totals",
    nflverse_reconstructed: "Reconstructed player scoring",
  };
  return labels[source] ?? source.replace(/_/g, " ");
}

function categoryLabel(category: string) {
  const labels: Record<string, string> = {
    data_quality: "data quality",
    league_size: "league size",
    participants: "managers",
    playoffs: "playoffs",
    roster_slots: "roster slots",
    schedule: "schedule",
    scoring_provenance: "scoring provenance",
    scoring_rules: "scoring rules",
    standings: "standings",
    waiver: "waivers",
  };
  return labels[category] ?? category.replace(/_/g, " ");
}

function ChangeList({ details }: { details: LeagueChangeDetail[] }) {
  if (details.length === 0) return null;
  return (
    <div className="space-y-2">
      {details.map((detail, index) => (
        <div key={`${detail.category}-${detail.title}-${index}`} className="rounded-[var(--radius-sm)] border border-[var(--border)] p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={detail.category === "data_quality" ? "gap" : "accent"}>{categoryLabel(detail.category)}</Badge>
            <span className="text-[var(--fs-sm)] font-semibold text-ink">{detail.title}</span>
          </div>
          <div className="mt-1 text-[var(--fs-sm)] text-muted">{detail.summary}</div>
          {(detail.before || detail.after) && (
            <div className="mt-2 grid gap-2 text-[var(--fs-xs)] text-faint sm:grid-cols-2">
              {detail.before && <div>Before: {detail.before}</div>}
              {detail.after && <div>After: {detail.after}</div>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function LeagueHistoryPage() {
  const timeline = useQuery({ queryKey: qk.leagueTimeline, queryFn: fetchTimeline });

  if (timeline.isError) {
    return <ErrorState message="Could not load league history." onRetry={() => timeline.refetch()} />;
  }

  const seasons = timeline.data?.seasons ?? [];
  const latest = seasons.at(-1);

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">League museum</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">League History</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          Season context, champions, schedule shape, and scoring provenance as preserved by the BFF.
        </p>
      </div>

      <Card className="p-5">
        {timeline.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat label="League" value={timeline.data?.league.name ?? "-"} />
            <Stat label="Seasons" value={timeline.data?.league.season_count ?? "-"} tone="accent" />
            <Stat label="Start" value={timeline.data?.league.start_year ?? "-"} />
            <Stat label="Latest" value={latest?.season_year ?? "-"} />
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          eyebrow="season by season"
          title="Timeline"
          action={
            <Link to="/rules" className="dz-badge dz-badge--accent">
              Rules &amp; Eras
            </Link>
          }
        />
        <div className="divide-y divide-[var(--hairline)]">
          {timeline.isLoading &&
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="m-5 h-20" />)}
          {seasons.map((season) => (
            <article key={season.season_id} className="grid gap-4 p-5 lg:grid-cols-[7rem_1fr_16rem]">
              <div>
                <div className="font-display text-[var(--fs-h2)] font-bold text-accent">
                  {season.season_year}
                </div>
                <Badge variant={season.is_scored ? "accent" : "gap"}>
                  {sourceLabel(season.scoring_provenance)}
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-[var(--fs-sm)] text-muted">{season.league_size}-team league</span>
                  <span className="text-[var(--fs-sm)] text-muted">
                    {season.regular_season_weeks ?? "?"} regular + {season.playoff_weeks ?? "?"} playoff weeks
                  </span>
                </div>
                <ChangeList details={season.changes.details} />
                {season.champion ? (
                  <Chip
                    name={season.champion.team_name ?? season.champion.owner_name}
                    sub={`Champion${season.champion.owner_name ? ` - ${season.champion.owner_name}` : ""}`}
                  />
                ) : (
                  <DataGap reason="champion_unavailable" />
                )}
              </div>
              <div className="text-[var(--fs-xs)] text-faint">
                <div>{season.verification_status.replace(/_/g, " ")}</div>
                <div>{season.source.replace(/_/g, " ")}</div>
              </div>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}
