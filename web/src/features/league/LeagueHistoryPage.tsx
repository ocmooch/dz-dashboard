import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Card, CardHeader, Chip, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type LeagueTimeline = components["schemas"]["LeagueTimeline"];
type LeagueTimelineSeason = components["schemas"]["LeagueTimelineSeason"];
type LeagueChangeDetail = components["schemas"]["LeagueChangeDetail"];
type CommissionerTerm = components["schemas"]["CommissionerTerm"];

async function fetchTimeline(): Promise<LeagueTimeline> {
  const { data, error } = await api.GET("/v1/league/timeline");
  if (error || !data) throw new Error("league timeline");
  return data.data;
}

async function fetchOverview(): Promise<components["schemas"]["LeagueOverview"]> {
  const { data, error } = await api.GET("/v1/league/overview");
  if (error || !data) throw new Error("league overview");
  return data.data;
}

function commissionerForYear(
  terms: CommissionerTerm[],
  year: number,
): CommissionerTerm | undefined {
  return terms.find((t) => t.from_year <= year && (t.to_year === null || t.to_year === undefined || t.to_year >= year));
}

function formatSchedule(reg?: number | null, po?: number | null): string {
  if (!reg && !po) return "";
  if (reg && po) return `${reg}-wk regular season · playoffs wk ${reg + 1}–${reg + po}`;
  if (reg) return `${reg}-wk regular season`;
  return `${po} playoff weeks`;
}

function CommissionerStrip({ terms }: { terms: CommissionerTerm[] }) {
  if (terms.length === 0) return null;
  return (
    <Card className="overflow-hidden">
      <CardHeader eyebrow="era by era" title="Commissioner History" />
      <div className="flex min-w-0 flex-wrap gap-0 divide-x divide-[var(--hairline)]">
        {terms.map((t) => {
          const isCurrent = t.to_year === null || t.to_year === undefined;
          return (
            <div
              key={`${t.owner_id}-${t.from_year}`}
              className="flex-1 min-w-[6rem] px-4 py-3 text-center"
            >
              <Link
                to={`/managers/${t.owner_id}`}
                className="block text-[var(--fs-sm)] font-semibold text-ink hover:text-accent transition-colors"
              >
                {t.owner_name}
              </Link>
              <div className="mt-0.5 text-[var(--fs-xs)] tabular-nums text-faint">
                {t.from_year}–{isCurrent ? "now" : t.to_year}
              </div>
              <div className="mt-1">
                {isCurrent ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-2)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
                    current
                  </span>
                ) : (
                  <span className="text-[10px] text-faint">
                    {t.seasons} {t.seasons === 1 ? "season" : "seasons"}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function categoryLabel(category: string) {
  const labels: Record<string, string> = {
    data_quality: "Data quality",
    league_size: "League structure",
    participants: "Managers",
    playoffs: "Playoffs",
    roster_slots: "Roster",
    schedule: "Schedule",
    scoring_provenance: "Scoring data",
    scoring_rules: "Scoring rules",
    standings: "Standings",
    waiver: "Waivers",
  };
  return labels[category] ?? category.replace(/_/g, " ");
}

type Impact = "high" | "medium" | "low";

function impactOf(category: string): Impact {
  if (category === "league_size" || category === "scoring_provenance") return "high";
  if (category === "schedule" || category === "waiver" || category === "standings" || category === "data_quality") return "low";
  return "medium";
}

const CATEGORY_COLOR: Record<string, string> = {
  league_size: "var(--warn)",
  scoring_provenance: "var(--info)",
  scoring_rules: "var(--accent)",
  roster_slots: "var(--series-5)",
  participants: "var(--win)",
  playoffs: "var(--series-2)",
  schedule: "var(--text-faint)",
  waiver: "var(--text-faint)",
  standings: "var(--text-faint)",
  data_quality: "var(--loss)",
};

function categoryColor(category: string): string {
  return CATEGORY_COLOR[category] ?? "var(--text-faint)";
}

function ChangeTimestamp({ changedAt }: { changedAt?: string | null }) {
  if (!changedAt) return null;
  const date = new Date(changedAt);
  if (isNaN(date.getTime())) return null;
  const formatted = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return <span className="text-[10px] tabular-nums text-faint">{formatted}</span>;
}

function DescriptionGapNote() {
  return (
    <div className="mt-1 text-[10px] text-faint italic">
      No detailed description available in transaction log.
    </div>
  );
}

function BeforeAfter({ before, after }: { before?: string | null; after?: string | null }) {
  if (!before && !after) return null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5 font-mono text-[var(--fs-xs)]">
      {before && (
        <span className="rounded bg-[var(--surface-3)] px-1.5 py-0.5 text-muted line-through">{before}</span>
      )}
      {before && after && <span className="text-faint">→</span>}
      {after && (
        <span className="rounded bg-[var(--surface-2)] px-1.5 py-0.5" style={{ color: "var(--win)" }}>
          {after}
        </span>
      )}
    </div>
  );
}

function ParticipantList({ detail }: { detail: LeagueChangeDetail }) {
  const joined = detail.participants_joined ?? [];
  const left = detail.participants_left ?? [];
  if (!joined.length && !left.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[var(--fs-xs)]">
      {joined.map((name) => (
        <span key={name} className="flex items-center gap-1" style={{ color: "var(--win)" }}>
          <span className="font-bold">+</span>{name}
        </span>
      ))}
      {left.map((name) => (
        <span key={name} className="flex items-center gap-1 text-faint line-through decoration-[var(--text-faint)]">
          {name}
        </span>
      ))}
    </div>
  );
}

function HighImpactChange({ detail }: { detail: LeagueChangeDetail }) {
  const color = categoryColor(detail.category);
  const isParticipant = detail.category === "participants";
  return (
    <div
      className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2.5"
      style={{ borderLeftColor: color, borderLeftWidth: 3 }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[var(--fs-xs)] font-semibold uppercase tracking-wide" style={{ color }}>
          {categoryLabel(detail.category)}
        </span>
        <span className="text-[var(--fs-sm)] font-semibold text-ink">{detail.title}</span>
        <ChangeTimestamp changedAt={detail.changed_at} />
      </div>
      {!isParticipant && detail.summary && (
        <div className="mt-0.5 text-[var(--fs-xs)] text-muted">{detail.summary}</div>
      )}
      {isParticipant ? (
        <ParticipantList detail={detail} />
      ) : (
        <BeforeAfter before={detail.before} after={detail.after} />
      )}
      {detail.description_gap && <DescriptionGapNote />}
    </div>
  );
}

function MediumChange({ detail }: { detail: LeagueChangeDetail }) {
  const color = categoryColor(detail.category);
  const isParticipant = detail.category === "participants";
  return (
    <div className="flex items-start gap-2.5 py-2 border-b border-[var(--hairline)] last:border-0">
      <span
        className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
        style={{ background: color }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="text-[var(--fs-xs)] font-semibold" style={{ color }}>
            {categoryLabel(detail.category)}
          </span>
          <span className="text-[var(--fs-sm)] text-ink">{detail.title}</span>
          <ChangeTimestamp changedAt={detail.changed_at} />
        </div>
        {!isParticipant && detail.summary && detail.summary !== detail.title && (
          <div className="text-[var(--fs-xs)] text-muted">{detail.summary}</div>
        )}
        {isParticipant ? (
          <ParticipantList detail={detail} />
        ) : (
          <BeforeAfter before={detail.before} after={detail.after} />
        )}
        {detail.description_gap && <DescriptionGapNote />}
      </div>
    </div>
  );
}

function RoutineChanges({ details }: { details: LeagueChangeDetail[] }) {
  const [open, setOpen] = useState(false);
  if (details.length === 0) return null;

  const typeList = [...new Set(details.map((d) => categoryLabel(d.category).toLowerCase()))].join(", ");

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[var(--fs-xs)] text-faint transition-colors hover:text-muted"
      >
        <span className="text-[10px]">{open ? "▾" : "▸"}</span>
        <span>
          {details.length} routine {details.length === 1 ? "change" : "changes"} — {typeList}
        </span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 border-l-2 border-[var(--hairline)] pl-3">
          {details.map((d, i) => (
            <div key={i} className="text-[var(--fs-xs)] text-faint">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="font-semibold text-muted">{d.title}</span>
                <ChangeTimestamp changedAt={d.changed_at} />
              </div>
              {d.summary && d.summary !== d.title && (
                <div className="mt-0.5 text-faint">{d.summary}</div>
              )}
              {(d.before || d.after) && (
                <span className="font-mono">
                  {d.before && <span className="text-faint line-through">{d.before}</span>}
                  {d.before && d.after && <span className="mx-1 text-faint">→</span>}
                  {d.after && <span className="text-muted">{d.after}</span>}
                </span>
              )}
              {d.description_gap && (
                <div className="text-[10px] italic">No detailed description available in transaction log.</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultsRow({ season }: { season: LeagueTimelineSeason }) {
  const { champion, runner_up, last_place } = season;
  if (!champion && !runner_up && !last_place) return <DataGap reason="champion_unavailable" />;

  return (
    <div className="flex flex-wrap items-start gap-3">
      {champion && (
        <Chip
          name={champion.team_name ?? champion.owner_name ?? "—"}
          sub={`Champion${champion.owner_name ? ` · ${champion.owner_name}` : ""}`}
          avatarUrl={teamAvatarUrl(champion.team_id)}
        />
      )}
      {(runner_up || last_place) && (
        <div className="flex flex-col gap-1.5 self-center">
          {runner_up && (
            <div className="flex items-center gap-2">
              <span className="w-16 text-[10px] font-semibold uppercase tracking-wide text-faint">
                Runner-up
              </span>
              <span className="text-[var(--fs-xs)] font-medium text-muted">
                {runner_up.team_name ?? runner_up.owner_name}
              </span>
            </div>
          )}
          {last_place && (
            <div className="flex items-center gap-2">
              <span className="w-16 text-[10px] font-semibold uppercase tracking-wide text-faint">
                Last place
              </span>
              <span className="text-[var(--fs-xs)] font-medium text-muted">
                {last_place.team_name ?? last_place.owner_name}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SeasonEntry({
  season,
  commissioner,
}: {
  season: LeagueTimelineSeason;
  commissioner?: CommissionerTerm;
}) {
  const details = season.changes.details;
  const high = details.filter((d) => impactOf(d.category) === "high");
  const medium = details.filter((d) => impactOf(d.category) === "medium");
  const low = details.filter((d) => impactOf(d.category) === "low");

  const totalChanges = details.length;

  return (
    <article className="grid gap-5 p-5 lg:grid-cols-[5.5rem_1fr]">
      {/* Left: year + quick meta */}
      <div className="shrink-0">
        <div className="font-display text-[var(--fs-h2)] font-bold tabular-nums text-accent">
          {season.season_year}
        </div>
        {season.regular_season_weeks || season.playoff_weeks ? (
          <div className="mt-1 text-[var(--fs-xs)] text-faint leading-relaxed">
            {formatSchedule(season.regular_season_weeks, season.playoff_weeks)}
          </div>
        ) : null}
        {commissioner && (
          <div className="mt-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-faint">
              Commish
            </div>
            <Link
              to={`/managers/${commissioner.owner_id}`}
              className="text-[var(--fs-xs)] font-medium text-muted hover:text-ink transition-colors"
            >
              {commissioner.owner_name}
            </Link>
          </div>
        )}
        {totalChanges > 0 && (
          <div
            className="mt-1.5 text-[var(--fs-xs)] tabular-nums"
            style={{ color: totalChanges > 3 ? "var(--warn)" : "var(--text-faint)" }}
          >
            {totalChanges} {totalChanges === 1 ? "change" : "changes"}
          </div>
        )}
      </div>

      {/* Right: results + changes */}
      <div className="space-y-3">
        <ResultsRow season={season} />

        {high.length > 0 && (
          <div className="space-y-2">
            {high.map((d, i) => (
              <HighImpactChange key={i} detail={d} />
            ))}
          </div>
        )}

        {medium.length > 0 && (
          <div className="rounded-[var(--radius-sm)] border border-[var(--hairline)] px-3 divide-y divide-[var(--hairline)]">
            {medium.map((d, i) => (
              <MediumChange key={i} detail={d} />
            ))}
          </div>
        )}

        <RoutineChanges details={low} />

        {totalChanges === 0 && (
          <div className="text-[var(--fs-xs)] text-faint italic">No material changes from prior season</div>
        )}
      </div>
    </article>
  );
}

export function LeagueHistoryPage() {
  const timeline = useQuery({ queryKey: qk.leagueTimeline, queryFn: fetchTimeline });
  const overview = useQuery({ queryKey: qk.leagueOverview, queryFn: fetchOverview });

  if (timeline.isError) {
    return <ErrorState message="Could not load league history." onRetry={() => timeline.refetch()} />;
  }

  // newest first for scroll-to-recent UX
  const seasons = [...(timeline.data?.seasons ?? [])].reverse();
  const latest = timeline.data?.seasons.at(-1);
  const commissioners = overview.data?.commissioners ?? [];

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">League museum</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">League History</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          Year-by-year changes: what shifted, what it was before, and how it compares. High-impact changes
          surface first; routine ones fold away.
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

      {/* Commissioner strip */}
      {overview.isLoading ? (
        <Skeleton className="h-24 w-full rounded-[var(--radius)]" />
      ) : (
        <CommissionerStrip terms={commissioners} />
      )}

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[var(--fs-xs)] text-faint">
        <span className="font-semibold text-muted">Change impact:</span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-1 rounded-sm" style={{ background: "var(--warn)" }} />
          League structure
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-1 rounded-sm" style={{ background: "var(--accent)" }} />
          Scoring rules
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: "var(--series-5)" }} />
          Roster
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: "var(--win)" }} />
          Managers
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: "var(--text-faint)" }} />
          Routine (collapsed)
        </span>
      </div>

      <Card>
        <CardHeader
          eyebrow="newest → oldest"
          title="Season Timeline"
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
            <SeasonEntry
              key={season.season_id}
              season={season}
              commissioner={
                season.season_year
                  ? commissionerForYear(commissioners, season.season_year)
                  : undefined
              }
            />
          ))}
        </div>
      </Card>
    </div>
  );
}
