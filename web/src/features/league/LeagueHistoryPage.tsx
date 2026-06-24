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
type LeagueEra = components["schemas"]["LeagueEra"];

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

async function fetchEras(): Promise<components["schemas"]["LeagueEras"]> {
  const { data, error } = await api.GET("/v1/league/eras");
  if (error || !data) throw new Error("league eras");
  return data.data;
}

function commissionerForYear(
  terms: CommissionerTerm[],
  year: number,
): CommissionerTerm | undefined {
  return terms.find((t) => t.from_year <= year && (t.to_year === null || t.to_year === undefined || t.to_year >= year));
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

// Eras: the league's playstyle history. Each era is a span of seasons sharing the
// rules that define how the game is played — reception scoring (PPR), the starting
// lineup's flex, and the waiver system. A new era begins only when one of those
// highly-significant rules changes; the caption names that change. Each cell links
// to that era's most-recent season below.
function EraStrip({ eras }: { eras: LeagueEra[] }) {
  if (eras.length === 0) return null;
  return (
    <Card className="overflow-hidden">
      <CardHeader eyebrow="playstyle history" title="Eras" />
      <div className="grid gap-px bg-[var(--hairline)] sm:grid-cols-2 lg:grid-cols-4">
        {eras.map((era, i) => {
          const span =
            era.start_year === era.end_year
              ? `${era.start_year}`
              : `${era.start_year}–${era.end_year}`;
          const traits = [era.ppr, era.lineup, era.waiver_system].filter(Boolean) as string[];
          const isCurrent = i === eras.length - 1;
          return (
            <a
              key={era.era_id}
              href={`#${era.era_id}`}
              className="group flex flex-col gap-2 bg-[var(--surface-1)] px-4 py-3 transition-colors hover:bg-[var(--surface-2)]"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-display text-[var(--fs-sm)] font-bold tabular-nums text-ink transition-colors group-hover:text-accent">
                  {span}
                </span>
                {isCurrent && (
                  <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
                    current
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1">
                {traits.map((t) => (
                  <span
                    key={t}
                    className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[var(--fs-xs)] text-muted"
                  >
                    {t}
                  </span>
                ))}
              </div>
              <div className="mt-auto text-[var(--fs-xs)] text-faint">
                {i > 0 && <span className="text-[10px] uppercase tracking-wide">Shift: </span>}
                {era.defining_change}
              </div>
            </a>
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
    draft: "Draft",
    trades: "Trades",
    money: "Money",
    admin: "Admin",
    commissioner: "Commissioner",
    transactions: "Transactions",
    divisions: "Divisions",
    league_event: "League event",
  };
  return labels[category] ?? category.replace(/_/g, " ");
}

const CATEGORY_COLOR: Record<string, string> = {
  league_size: "var(--warn)",
  scoring_provenance: "var(--info)",
  scoring_rules: "var(--accent)",
  roster_slots: "var(--series-5)",
  participants: "var(--win)",
  playoffs: "var(--series-2)",
  schedule: "var(--text-faint)",
  waiver: "var(--series-3)",
  standings: "var(--text-faint)",
  data_quality: "var(--loss)",
  draft: "var(--series-4)",
  trades: "var(--series-1)",
  money: "var(--win)",
  admin: "var(--text-faint)",
  commissioner: "var(--series-2)",
  transactions: "var(--series-3)",
  divisions: "var(--warn)",
  league_event: "var(--accent)",
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

const SOURCE_LABELS: Record<string, string> = {
  derived_from_db: "Derived from league database",
  nfl_com_transaction_log: "NFL.com transaction log",
  nfl_com_authoritative_total: "NFL.com season totals",
  nflverse_reconstructed: "Reconstructed player scoring",
  league_ruling: "League ruling (public record)",
};

const CERTAINTY_LABELS: Record<string, string> = {
  verified: "Verified from records",
  source_limited: "Source-limited — inferred from partial data",
  identity_source_limited: "Identity source-limited — manager mapping incomplete",
};

function sourceLabel(value: string): string {
  return SOURCE_LABELS[value] ?? value.replace(/_/g, " ");
}

function certaintyLabel(value: string): string {
  return CERTAINTY_LABELS[value] ?? value.replace(/_/g, " ");
}

const TIER_RANK: Record<string, number> = { T1: 0, T2: 1, T3: 2 };

function tierOf(detail: LeagueChangeDetail): string {
  return detail.tier ?? "T3";
}

function InSeasonMarker() {
  return (
    <span
      className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
      style={{ background: "color-mix(in srgb, var(--loss) 15%, transparent)", color: "var(--loss)" }}
      title="Changed once the season was already underway"
    >
      in-season
    </span>
  );
}

// A nested sub-row inside an expanded aggregated event or routine bucket.
function MemberRow({ detail }: { detail: LeagueChangeDetail }) {
  return (
    <div className="flex flex-col gap-0.5 px-3 py-1.5 border-b border-[var(--hairline)] last:border-0">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-[var(--fs-xs)] font-semibold text-muted">
          {detail.human_label ?? detail.title}
        </span>
        <ChangeTimestamp changedAt={detail.changed_at} />
        {detail.phase === "in_season" && <InSeasonMarker />}
      </div>
      <div className="text-[var(--fs-xs)] text-faint">{detail.summary}</div>
      <BeforeAfter before={detail.before} after={detail.after} />
    </div>
  );
}

// One row per change/event with a three-tier visual weight so the eye can triage:
// T1 (Major) is highlighted and badged, T2 (Notable) is a clean mid-weight row, and
// T3 (Routine) recedes — dim text, hairline rule. The in-season marker flags
// post-kickoff changes; aggregated events and the per-season routine bucket expand
// to their member rows; unrecoverable detail surfaces a "context not recorded"
// affordance — never a fabricated value. Before/after chips show only when the
// summary sentence doesn't already carry the change, so a row never says it twice.
function ChangeRow({ detail }: { detail: LeagueChangeDetail }) {
  const [open, setOpen] = useState(false);
  const color = categoryColor(detail.category);
  const isParticipant = detail.category === "participants";
  const members = detail.members ?? [];
  const hasMembers = members.length > 0;
  const tier = tierOf(detail);
  const isMajor = tier === "T1";
  const isRoutine = tier === "T3";
  const inSeason = detail.phase === "in_season";

  const brief =
    detail.summary && detail.summary !== detail.title && detail.summary !== detail.after
      ? detail.summary
      : null;

  const provExpandable =
    detail.certainty !== "verified" ||
    detail.source !== "derived_from_db" ||
    detail.description_gap;
  const expandable = hasMembers || provExpandable;

  // Tier-driven weight. T1 shouts (fill + thick rule), T2 speaks (category rule),
  // T3 whispers (thin hairline rule, muted text).
  const borderWidth = isMajor ? 4 : isRoutine ? 2 : 3;
  const borderColor = isRoutine ? "var(--hairline)" : color;
  const titleClass = isMajor
    ? "font-bold text-ink"
    : isRoutine
      ? "font-medium text-muted"
      : "font-semibold text-ink";

  return (
    <div
      className="px-3 py-2.5 border-b border-[var(--hairline)] last:border-0"
      style={{
        borderLeft: `${borderWidth}px solid ${borderColor}`,
        background: isMajor ? "color-mix(in srgb, var(--surface-2) 60%, transparent)" : undefined,
      }}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span
          className="text-[var(--fs-xs)] font-semibold uppercase tracking-wide"
          style={{ color: isRoutine ? "var(--text-faint)" : color }}
        >
          {categoryLabel(detail.category)}
        </span>
        {isMajor && (
          <span
            className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
            style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent)" }}
          >
            Major
          </span>
        )}
        <span className={`text-[var(--fs-sm)] ${titleClass}`}>
          {detail.human_label ?? detail.title}
        </span>
        <ChangeTimestamp changedAt={detail.changed_at} />
        {inSeason && <InSeasonMarker />}
        {expandable && (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="ml-auto flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-faint transition-colors hover:text-muted"
          >
            {hasMembers ? (open ? "Hide" : `Show ${members.length}`) : open ? "Less" : "More"}
            <span className="text-[10px]">{open ? "▾" : "▸"}</span>
          </button>
        )}
      </div>

      {isParticipant ? (
        <ParticipantList detail={detail} />
      ) : brief ? (
        <div className="mt-0.5 text-[var(--fs-xs)] text-muted">{brief}</div>
      ) : (
        <BeforeAfter before={detail.before} after={detail.after} />
      )}

      {detail.missing_context && (
        <div className="mt-1 text-[var(--fs-xs)] italic text-faint">
          Context not recorded — NFL.com logged the action but not the detail.
        </div>
      )}

      {open && hasMembers && (
        <div className="mt-2 overflow-hidden rounded-[var(--radius-sm)] border border-[var(--hairline)] bg-[var(--surface-1)]">
          {members.map((m, i) => (
            <MemberRow key={`${m.canonical_type ?? m.category}-${i}`} detail={m} />
          ))}
        </div>
      )}

      {open && provExpandable && (
        <div className="mt-2 space-y-1 rounded-[var(--radius-sm)] bg-[var(--surface-2)] px-2.5 py-2 text-[var(--fs-xs)] text-faint">
          <div>
            <span className="font-semibold text-muted">Source:</span> {sourceLabel(detail.source)}
          </div>
          <div>
            <span className="font-semibold text-muted">Certainty:</span> {certaintyLabel(detail.certainty)}
          </div>
        </div>
      )}
    </div>
  );
}

function ResultsRow({ season }: { season: LeagueTimelineSeason }) {
  const { champion, runner_up, last_place, sacko } = season;
  if (!champion && !runner_up && !last_place && !sacko)
    return <DataGap reason="champion_unavailable" />;

  return (
    <div className="flex flex-wrap items-start gap-3">
      {champion && (
        <Chip
          name={champion.team_name ?? champion.owner_name ?? "—"}
          sub={`Champion${champion.owner_name ? ` · ${champion.owner_name}` : ""}`}
          avatarUrl={teamAvatarUrl(champion.team_id)}
        />
      )}
      {(runner_up || last_place || sacko) && (
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
          {sacko ? (
            <div
              className="flex items-center gap-2"
              title={
                sacko.source === "recorded"
                  ? "Recorded last-place team (bracket could not be split)"
                  : "Toilet-bowl loser"
              }
            >
              <span className="w-16 text-[10px] font-semibold uppercase tracking-wide text-faint">
                Sacko 💩
              </span>
              <span className="text-[var(--fs-xs)] font-medium text-muted">
                {sacko.team_name ?? sacko.owner_name}
              </span>
            </div>
          ) : (
            last_place && (
              <div className="flex items-center gap-2">
                <span className="w-16 text-[10px] font-semibold uppercase tracking-wide text-faint">
                  Last place
                </span>
                <span className="text-[var(--fs-xs)] font-medium text-muted">
                  {last_place.team_name ?? last_place.owner_name}
                </span>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

function SeasonEntry({
  season,
  commissioner,
  anchorId,
}: {
  season: LeagueTimelineSeason;
  commissioner?: CommissionerTerm;
  anchorId?: string;
}) {
  const details = [...season.changes.details].sort(
    (a, b) => (TIER_RANK[tierOf(a)] ?? 9) - (TIER_RANK[tierOf(b)] ?? 9),
  );
  // Count leaf changes (an aggregated event / routine bucket counts its members).
  const totalChanges = details.reduce(
    (sum, d) => sum + ((d.members?.length ?? 0) || 1),
    0,
  );

  return (
    <article id={anchorId} className="grid scroll-mt-24 gap-5 p-5 lg:grid-cols-[5.5rem_1fr]">
      {/* Left: year + quick meta */}
      <div className="shrink-0">
        <div className="font-display text-[var(--fs-h2)] font-bold tabular-nums text-accent">
          {season.season_year}
        </div>
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

        {totalChanges > 0 ? (
          <div className="overflow-hidden rounded-[var(--radius-sm)] border border-[var(--hairline)]">
            {details.map((d, i) => (
              <ChangeRow key={`${d.category}-${d.title}-${i}`} detail={d} />
            ))}
          </div>
        ) : (
          <div className="text-[var(--fs-xs)] text-faint italic">No material changes from prior season</div>
        )}
      </div>
    </article>
  );
}

export function LeagueHistoryPage() {
  const timeline = useQuery({ queryKey: qk.leagueTimeline, queryFn: fetchTimeline });
  const overview = useQuery({ queryKey: qk.leagueOverview, queryFn: fetchOverview });
  const erasQuery = useQuery({ queryKey: qk.leagueEras, queryFn: fetchEras });

  if (timeline.isError) {
    return <ErrorState message="Could not load the league timeline." onRetry={() => timeline.refetch()} />;
  }

  // newest first for scroll-to-recent UX
  const seasons = [...(timeline.data?.seasons ?? [])].reverse();
  const latest = timeline.data?.seasons.at(-1);
  const commissioners = overview.data?.commissioners ?? [];
  const eras = erasQuery.data?.eras ?? [];

  // Anchor each era to its most-recent season so the strip's cells scroll into place.
  const eraAnchorBySeasonId = new Map<number, string>();
  const seenEra = new Set<string>();
  for (const s of seasons) {
    if (!seenEra.has(s.era_id)) {
      seenEra.add(s.era_id);
      eraAnchorBySeasonId.set(s.season_id, s.era_id);
    }
  }

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">League museum</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">League Timeline</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          Every season, newest first, grouped into <span className="font-semibold text-ink">eras</span> — spans
          of consistent playstyle bounded by the rules that matter most (PPR, lineup, waivers).{" "}
          <span className="font-semibold text-ink">Major</span> changes are highlighted,{" "}
          <span className="font-semibold text-ink">notable</span> ones sit below them, and routine admin edits
          collapse into one group per season. Changes made after kickoff carry an{" "}
          <span className="font-semibold text-ink">in-season</span> marker. Only what the database can prove —
          gaps stay labelled, nothing is dropped.
        </p>
      </div>

      <Card className="p-5">
        {timeline.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat label="League" value={timeline.data?.league.name ?? "-"} />
            <Stat label="Seasons" value={timeline.data?.league.season_count ?? "-"} tone="accent" />
            <Stat
              label="Span"
              value={
                timeline.data?.league.start_year
                  ? `${timeline.data.league.start_year}–${latest?.season_year ?? "-"}`
                  : "-"
              }
            />
            <Stat label="Eras" value={eras.length || "-"} />
          </div>
        )}
      </Card>

      {/* Eras — playstyle history strip above the timeline */}
      {erasQuery.isLoading ? (
        <Skeleton className="h-24 w-full rounded-[var(--radius)]" />
      ) : (
        <EraStrip eras={eras} />
      )}

      {/* Commissioner strip */}
      {overview.isLoading ? (
        <Skeleton className="h-24 w-full rounded-[var(--radius)]" />
      ) : (
        <CommissionerStrip terms={commissioners} />
      )}

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[var(--fs-xs)] text-faint">
        <span className="font-semibold text-muted">Reading the timeline:</span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
            style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent)" }}
          >
            Major
          </span>
          game-defining change
        </span>
        <span className="flex items-center gap-1.5">
          <InSeasonMarker />
          made after kickoff
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-faint">Show N ▸</span>
          expand a grouped event
        </span>
      </div>

      <Card>
        <CardHeader eyebrow="newest → oldest" title="Season Timeline" />
        <div className="divide-y divide-[var(--hairline)]">
          {timeline.isLoading &&
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="m-5 h-20" />)}
          {seasons.map((season) => (
            <SeasonEntry
              key={season.season_id}
              season={season}
              anchorId={eraAnchorBySeasonId.get(season.season_id)}
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
