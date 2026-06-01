import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, Chip, ErrorState, RecordLine, Skeleton, Trophy } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { num, ordinal, pct } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type OwnerCareer = components["schemas"]["OwnerCareer"];

async function fetchOwners() {
  const { data, error } = await api.GET("/v1/owners");
  if (error || !data) throw new Error("Failed to load managers");
  return data.data.owners;
}

/** Win rate over decided games. Returns null when a manager has no games on
 *  record (e.g. an owner with only unscored, record-only context) so we never
 *  render a fake 0%. */
function winPct(o: OwnerCareer): number | null {
  const games = o.total_wins + o.total_losses + o.total_ties;
  return games > 0 ? o.total_wins / games : null;
}

// The career table sorts client-side; the BFF's default order (titles → wins →
// PF) is the initial view. Each column knows how to rank a career.
type SortKey = "titles" | "winPct" | "points" | "seasons" | "bestFinish" | "avgFinish";
const SORTERS: Record<SortKey, (a: OwnerCareer, b: OwnerCareer) => number> = {
  titles: (a, b) => b.championships - a.championships || b.total_wins - a.total_wins,
  winPct: (a, b) => (winPct(b) ?? -1) - (winPct(a) ?? -1),
  points: (a, b) => b.total_points_for - a.total_points_for,
  seasons: (a, b) => b.seasons_played - a.seasons_played,
  // Finishes are "lower is better", and a missing finish sorts last.
  bestFinish: (a, b) => (a.best_finish ?? Infinity) - (b.best_finish ?? Infinity),
  avgFinish: (a, b) => (a.avg_finish ?? Infinity) - (b.avg_finish ?? Infinity),
};

function LegendCard({ label, name, value }: { label: string; name: string | null | undefined; value: string }) {
  return (
    <Card className="p-4">
      <div className="dz-eyebrow mb-2">{label}</div>
      <div className="num text-[var(--fs-h3)] font-bold leading-none text-accent">{value}</div>
      <div className="mt-1 truncate text-[var(--fs-sm)] text-muted">{name ?? "—"}</div>
    </Card>
  );
}

/** The four league-wide superlatives, computed from the career list. Owner-centric
 *  by design — distinct from the event-centric Records Book. */
function LeagueLegends({ owners }: { owners: OwnerCareer[] }) {
  const top = <K,>(score: (o: OwnerCareer) => K, cmp: (a: K, b: K) => number) =>
    owners.reduce((best, o) => (cmp(score(o), score(best)) > 0 ? o : best), owners[0]);

  const mostTitles = top((o) => o.championships, (a, b) => a - b);
  const bestWinPct = top((o) => winPct(o) ?? -1, (a, b) => a - b);
  const mostPoints = top((o) => o.total_points_for, (a, b) => a - b);
  const mostSeasons = top((o) => o.seasons_played, (a, b) => a - b);

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <LegendCard label="Most titles" name={mostTitles.display_name} value={`${mostTitles.championships} ★`} />
      <LegendCard label="Best win %" name={bestWinPct.display_name} value={pct(winPct(bestWinPct))} />
      <LegendCard label="Most points" name={mostPoints.display_name} value={num(mostPoints.total_points_for, 0)} />
      <LegendCard label="Most seasons" name={mostSeasons.display_name} value={`${mostSeasons.seasons_played}`} />
    </div>
  );
}

function SortHeader({
  label,
  k,
  active,
  onSort,
  align = "right",
}: {
  label: string;
  k: SortKey;
  active: SortKey;
  onSort: (k: SortKey) => void;
  align?: "left" | "right";
}) {
  return (
    <th className={align === "right" ? "dz-num" : undefined}>
      <button
        type="button"
        onClick={() => onSort(k)}
        className={`inline-flex items-center gap-1 hover:text-text ${active === k ? "text-accent" : ""}`}
        aria-pressed={active === k}
      >
        {label}
        {active === k && <span aria-hidden>▾</span>}
      </button>
    </th>
  );
}

export function ManagersPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.owners,
    queryFn: fetchOwners,
  });
  const [sort, setSort] = useState<SortKey>("titles");

  const owners = useMemo(() => (data ? [...data].sort(SORTERS[sort]) : []), [data, sort]);

  return (
    <div className="dz-rise space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">All-time</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Managers</h1>
        </div>
        {data && <Badge>{data.length} managers</Badge>}
      </div>

      {isLoading && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </>
      )}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data && data.length > 0 && (
        <>
          <LeagueLegends owners={data} />

          <Card>
            <CardHeader eyebrow="career ledger" title="Every Manager" />
            <div className="overflow-x-auto p-1">
              <table className="dz-table w-full">
                <thead>
                  <tr>
                    <th>Manager</th>
                    <SortHeader label="Seasons" k="seasons" active={sort} onSort={setSort} />
                    <SortHeader label="Win %" k="winPct" active={sort} onSort={setSort} />
                    <th className="dz-num">Record</th>
                    <SortHeader label="Points For" k="points" active={sort} onSort={setSort} />
                    <SortHeader label="Titles" k="titles" active={sort} onSort={setSort} />
                    <SortHeader label="Best" k="bestFinish" active={sort} onSort={setSort} />
                    <SortHeader label="Avg finish" k="avgFinish" active={sort} onSort={setSort} />
                  </tr>
                </thead>
                <tbody>
                  {owners.map((o) => (
                    <tr key={o.owner_id}>
                      <td>
                        <Link to={`/managers/${o.owner_id}`} className="hover:text-accent">
                          <Chip name={o.display_name} />
                        </Link>
                      </td>
                      <td className="dz-num num">{o.seasons_played}</td>
                      <td className="dz-num num">{pct(winPct(o))}</td>
                      <td className="dz-num">
                        <RecordLine wins={o.total_wins} losses={o.total_losses} ties={o.total_ties} />
                      </td>
                      <td className="dz-num num">{num(o.total_points_for, 0)}</td>
                      <td className="dz-num">{o.championships > 0 ? <Trophy count={o.championships} /> : "—"}</td>
                      <td className="dz-num num">{ordinal(o.best_finish)}</td>
                      <td className="dz-num num">{o.avg_finish == null ? "—" : o.avg_finish.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
