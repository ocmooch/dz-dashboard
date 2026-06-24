import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, Chip, ErrorState, RecordLine, Skeleton, Trophy } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { num, ordinal, pct, teamAvatarUrl } from "@/lib/format";
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
type SortDir = "asc" | "desc";

// Rate-based columns where a short stint can flatter a manager (a 1-season owner
// with a fluky finish or win rate). For these we rank in three tiers — active
// managers, then departed-but-long-tenured (the BFF's `qualified` flag covers
// active OR a significant stint), then short-stint departed — so an active
// manager always sits above any former one, even one below the stint threshold,
// and no short stint floats to the top. Owners stay listed, never crowned above
// an active or legacy manager. Accumulation columns (titles/points/seasons) need
// no gate: a short stint can't out-accumulate a long one.
const GATED_SORTS = new Set<SortKey>(["winPct", "bestFinish", "avgFinish"]);
const SORTERS: Record<SortKey, (a: OwnerCareer, b: OwnerCareer) => number> = {
  titles: (a, b) => a.championships - b.championships || a.total_wins - b.total_wins,
  winPct: (a, b) => (winPct(a) ?? -1) - (winPct(b) ?? -1),
  points: (a, b) => a.total_points_for - b.total_points_for,
  seasons: (a, b) => a.seasons_played - b.seasons_played,
  // Finishes are "lower is better", and a missing finish sorts last.
  bestFinish: (a, b) => (b.best_finish ?? Infinity) - (a.best_finish ?? Infinity),
  avgFinish: (a, b) => (b.avg_finish ?? Infinity) - (a.avg_finish ?? Infinity),
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
  const top = <K,>(pool: OwnerCareer[], score: (o: OwnerCareer) => K, cmp: (a: K, b: K) => number) =>
    pool.reduce((best, o) => (cmp(score(o), score(best)) > 0 ? o : best), pool[0]);

  // Best win % crowns only qualified managers (active or a significant stint) so a
  // one-season hot streak never tops the legends; the accumulation legends are
  // tenure-proof and stay over everyone. Fall back to all if none qualify.
  const eligible = owners.filter((o) => o.qualified);
  const winPctPool = eligible.length > 0 ? eligible : owners;

  const mostTitles = top(owners, (o) => o.championships, (a, b) => a - b);
  const bestWinPct = top(winPctPool, (o) => winPct(o) ?? -1, (a, b) => a - b);
  const mostPoints = top(owners, (o) => o.total_points_for, (a, b) => a - b);
  const mostSeasons = top(owners, (o) => o.seasons_played, (a, b) => a - b);

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
  dir,
  onSort,
  align = "right",
}: {
  label: string;
  k: SortKey;
  active: SortKey;
  dir: SortDir;
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
        aria-label={`${label} sort ${active === k ? dir : "inactive"}`}
      >
        {label}
        {active === k && <span aria-hidden>{dir === "asc" ? "▴" : "▾"}</span>}
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
  const [dir, setDir] = useState<SortDir>("desc");

  const owners = useMemo(() => {
    if (!data) return [];
    const order = (arr: OwnerCareer[]) => {
      const s = [...arr].sort(SORTERS[sort]);
      return dir === "asc" ? s : s.reverse();
    };
    // On rate-based columns, rank in three tiers (in either direction) so a short
    // stint never floats to the top and an active manager always outranks a former
    // one: active first, then departed-but-qualified (significant stint), then
    // short-stint departed. Otherwise a single pass over everyone.
    if (!GATED_SORTS.has(sort)) return order(data);
    return [
      ...order(data.filter((o) => o.is_active)),
      ...order(data.filter((o) => !o.is_active && o.qualified)),
      ...order(data.filter((o) => !o.is_active && !o.qualified)),
    ];
  }, [data, sort, dir]);

  const onSort = (k: SortKey) => {
    if (k === sort) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSort(k);
      setDir("desc");
    }
  };

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
                    <SortHeader label="Seasons" k="seasons" active={sort} dir={dir} onSort={onSort} />
                    <SortHeader label="Win %" k="winPct" active={sort} dir={dir} onSort={onSort} />
                    <th className="dz-num">Record</th>
                    <SortHeader label="Points For" k="points" active={sort} dir={dir} onSort={onSort} />
                    <SortHeader label="Titles" k="titles" active={sort} dir={dir} onSort={onSort} />
                    <SortHeader label="Best" k="bestFinish" active={sort} dir={dir} onSort={onSort} />
                    <SortHeader label="Avg finish" k="avgFinish" active={sort} dir={dir} onSort={onSort} />
                  </tr>
                </thead>
                <tbody>
                  {owners.map((o) => (
                    <tr key={o.owner_id} className={o.qualified ? undefined : "opacity-60"}>
                      <td>
                        <Link
                          to={`/managers/${o.owner_id}`}
                          className="inline-flex items-center gap-2 hover:text-accent"
                        >
                          <Chip name={o.display_name} avatarUrl={teamAvatarUrl(o.latest_team_id)} />
                          {!o.is_active && (
                            <span className="dz-eyebrow text-faint" title="No longer in the league">
                              former
                            </span>
                          )}
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
            <p className="px-4 pb-4 pt-1 text-[var(--fs-xs)] text-faint">
              When sorting by win %, best, or average finish, active managers are
              listed first, then former managers with a long stint, then those with a
              short stint who have left — a one- or two-season run can flatter a rate,
              so it never ranks above an active or long-tenured manager. Every manager
              is still shown; “former” marks those no longer in the league.
            </p>
          </Card>
        </>
      )}
    </div>
  );
}
