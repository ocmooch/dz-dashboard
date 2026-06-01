import { useQuery } from "@tanstack/react-query";

import { Badge, Card, CardHeader, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

async function fetchMeta() {
  const { data, error } = await api.GET("/v1/meta");
  if (error || !data) throw new Error("Failed to load coverage");
  return data.data;
}

function yearRange(years: number[]): string {
  if (years.length === 0) return "—";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? `${lo}` : `${lo}–${hi}`;
}

/** One row in the reliability map: a data domain, its honest status, and the note. */
function GapRow({
  domain,
  status,
  tone,
  note,
}: {
  domain: string;
  status: string;
  tone: "win" | "loss" | "gap" | "accent";
  note: string;
}) {
  return (
    <tr>
      <td className="font-medium text-text">{domain}</td>
      <td>
        <Badge variant={tone}>{status}</Badge>
      </td>
      <td className="text-muted">{note}</td>
    </tr>
  );
}

/** Coverage / About (`/about`) — the honesty layer's home page. Renders what the
 *  database actually contains from /v1/meta, the known gaps drawn from the Phase 1
 *  reliability map, and the source attribution Phase 1 obliges us to surface. */
export function AboutPage() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: qk.meta, queryFn: fetchMeta });

  return (
    <div className="dz-rise space-y-4">
      <div>
        <div className="dz-eyebrow mb-1">the honest picture</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Coverage &amp; About</h1>
        <p className="mt-2 max-w-2xl text-muted">
          What this dashboard knows, how fresh it is, and where the data genuinely runs out. Nothing
          here is fabricated — absent data is labeled, never shown as a zero.
        </p>
      </div>

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data && (
        <>
          <Card className="p-5">
            <CardHeader eyebrow="freshness" title="Latest pipeline run" />
            <div className="grid grid-cols-2 gap-5 p-1 sm:grid-cols-4">
              <Stat
                label="status"
                value={data.latest_run.status ?? "—"}
                tone={data.latest_run.status === "success" ? "win" : "loss"}
              />
              <Stat label="mode" value={data.latest_run.mode ?? "—"} />
              <Stat
                label="finished"
                value={
                  data.latest_run.finished_at
                    ? new Date(data.latest_run.finished_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })
                    : "—"
                }
              />
              <Stat
                label="run"
                value={data.latest_run.run_id != null ? `#${data.latest_run.run_id}` : "—"}
              />
            </div>
          </Card>

          <Card className="p-5">
            <CardHeader eyebrow="what's in the database" title="Season coverage" />
            <div className="grid grid-cols-1 gap-5 p-1 sm:grid-cols-3">
              <Stat label="seasons on record" value={yearRange(data.coverage.seasons_present)} />
              <Stat
                label="scored seasons"
                value={yearRange(data.coverage.seasons_scored)}
                tone="accent"
              />
              <Stat
                label="historical reconstruction"
                value={data.coverage.reconstruction_complete ? "complete" : "pending"}
                tone={data.coverage.reconstruction_complete ? "win" : "loss"}
              />
            </div>
            <p className="px-1 pt-3 text-[var(--fs-sm)] text-muted">
              League scoring begins in {data.coverage.scored_year_min ?? "—"}. Earlier seasons exist
              as records but were never scored — those views show a data-gap marker, not a zero.
            </p>
          </Card>

          <Card>
            <CardHeader eyebrow="reliability map" title="Known gaps" />
            <div className="overflow-x-auto">
              <table className="dz-table">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Status</th>
                    <th>What it means</th>
                  </tr>
                </thead>
                <tbody>
                  <GapRow
                    domain="Raw weekly stats (nflverse)"
                    status="solid"
                    tone="win"
                    note="2010–present, every season. Used freely."
                  />
                  <GapRow
                    domain="Scored fantasy points"
                    status={`scored ${yearRange(data.coverage.seasons_scored)}`}
                    tone="accent"
                    note={`Pre-${data.coverage.scored_year_min ?? "scored-era"} seasons render as “not scored”, never as 0 points.`}
                  />
                  <GapRow
                    domain="Standings, lineups & matchups"
                    status={data.coverage.reconstruction_complete ? "reconstructed" : "pending"}
                    tone={data.coverage.reconstruction_complete ? "win" : "loss"}
                    note={
                      data.coverage.reconstruction_complete
                        ? "Champions, records, and box scores filled by the reconstruction run."
                        : "Reconstruction still finishing — some seasons show “metadata pending”."
                    }
                  />
                  <GapRow
                    domain="Player availability (FA / owned)"
                    status={data.coverage.availability_current_season_only ? "current season only" : "full history"}
                    tone={data.coverage.availability_current_season_only ? "gap" : "win"}
                    note="History was never snapshotted; past-season availability is not reconstructable."
                  />
                  <GapRow
                    domain="Team-defense / DST scoring"
                    status={data.coverage.dst_scoring_complete ? "scored" : "not scored"}
                    tone={data.coverage.dst_scoring_complete ? "win" : "gap"}
                    note="No nflverse team-defense rollups; DST slots are marked as a known gap."
                  />
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="p-5">
            <CardHeader eyebrow="provenance" title="Sources & attribution" />
            <div className="space-y-4 p-1 text-muted">
              <div>
                <div className="font-medium text-text">nflverse</div>
                <p className="text-[var(--fs-sm)]">
                  Raw weekly NFL player statistics and identifiers. Released under{" "}
                  <a
                    className="text-accent hover:underline"
                    href="https://creativecommons.org/licenses/by/4.0/"
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    CC&nbsp;BY&nbsp;4.0
                  </a>
                  .
                </p>
              </div>
              <div>
                <div className="font-medium text-text">Sleeper</div>
                <p className="text-[var(--fs-sm)]">
                  Player identity cross-IDs, projections, and trending-player signals.
                </p>
              </div>
              <p className="border-t border-[var(--border)] pt-3 text-[var(--fs-sm)] text-faint">
                This dashboard reads only the Phase&nbsp;1 pipeline database. It never calls
                NFL.com, nflverse, or Sleeper directly, and never writes back.
              </p>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
