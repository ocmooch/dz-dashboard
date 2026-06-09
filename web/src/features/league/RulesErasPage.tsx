import { useQuery } from "@tanstack/react-query";

import { Badge, Card, CardHeader, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { qk } from "@/lib/queryKeys";

type LeagueEras = components["schemas"]["LeagueEras"];
type LeagueChangeDetail = components["schemas"]["LeagueChangeDetail"];

async function fetchEras(): Promise<LeagueEras> {
  const { data, error } = await api.GET("/v1/league/eras");
  if (error || !data) throw new Error("league eras");
  return data.data;
}

function provenanceLabel(value: string) {
  const labels: Record<string, string> = {
    nfl_com_authoritative_total: "NFL.com team totals",
    nflverse_reconstructed: "Reconstructed player scoring",
  };
  return labels[value] ?? value.replace(/_/g, " ");
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

function ChangeDetailRows({ details }: { details: LeagueChangeDetail[] }) {
  return (
    <div className="mt-3 space-y-3">
      {details.map((detail, index) => (
        <div key={`${detail.category}-${detail.title}-${index}`} className="rounded-[var(--radius-sm)] border border-[var(--hairline)] p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={detail.category === "data_quality" ? "gap" : "accent"}>{categoryLabel(detail.category)}</Badge>
            <span className="text-[var(--fs-sm)] font-semibold text-ink">{detail.title}</span>
          </div>
          <div className="mt-1 text-[var(--fs-sm)] text-muted">{detail.summary}</div>
          {(detail.before || detail.after) && (
            <div className="mt-2 grid gap-2 text-[var(--fs-xs)] text-faint">
              {detail.before && <div>Before: {detail.before}</div>}
              {detail.after && <div>After: {detail.after}</div>}
            </div>
          )}
          <div className="mt-2 text-[var(--fs-xs)] text-faint">
            {detail.source.replace(/_/g, " ")} · {detail.certainty.replace(/_/g, " ")}
          </div>
        </div>
      ))}
    </div>
  );
}

export function RulesErasPage() {
  const eras = useQuery({ queryKey: qk.leagueEras, queryFn: fetchEras });

  if (eras.isError) {
    return <ErrorState message="Could not load rules and eras." onRetry={() => eras.refetch()} />;
  }

  const rows = eras.data?.eras ?? [];
  const changes = eras.data?.changes ?? [];

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Context lab</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Rules &amp; Eras</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          Era labels are derived from material context the database can prove today. Missing detailed
          scoring and roster-slot rules stay labelled instead of filled in.
        </p>
      </div>

      <Card className="p-5">
        {eras.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat label="Eras" value={rows.length} tone="accent" />
            <Stat label="Changes" value={changes.length} />
            <Stat label="League" value={eras.data?.league.name ?? "-"} />
            <Stat label="Span" value={`${eras.data?.league.start_year ?? "-"}-${eras.data?.league.current_year ?? "-"}`} />
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_24rem]">
        <Card>
          <CardHeader eyebrow="era-aware comparisons" title="Known Eras" />
          <div className="divide-y divide-[var(--hairline)]">
            {eras.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="m-5 h-24" />)}
            {rows.map((era) => (
              <article key={era.era_id} className="space-y-4 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-display text-[var(--fs-h3)] font-bold uppercase tracking-wide">
                      {era.label}
                    </div>
                    <div className="text-[var(--fs-xs)] text-faint">
                      {era.start_year === era.end_year ? era.start_year : `${era.start_year}-${era.end_year}`}
                    </div>
                  </div>
                  <Badge variant={era.verification_status === "known_source_gap" ? "gap" : "accent"}>
                    {era.verification_status.replace(/_/g, " ")}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Stat label="Teams" value={era.league_size} />
                  <Stat label="Regular" value={era.regular_season_weeks ?? "-"} unit="weeks" />
                  <Stat label="Playoff" value={era.playoff_weeks ?? "-"} unit="weeks" />
                  <Stat label="Source" value={provenanceLabel(era.scoring_provenance)} />
                </div>
              </article>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader eyebrow="change log" title="Material Changes" />
          <div className="space-y-3 p-5">
            {changes.length === 0 && !eras.isLoading && <DataGap reason="no_material_changes" />}
            {changes.map((change) => (
              <div key={change.season_year} className="rounded-[var(--radius-sm)] border border-[var(--border)] p-3">
                <div className="font-display text-[var(--fs-h3)] font-bold text-accent">{change.season_year}</div>
                <ChangeDetailRows details={change.details} />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
