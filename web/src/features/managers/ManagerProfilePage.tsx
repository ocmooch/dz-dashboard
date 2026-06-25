import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { RankFlow } from "@/charts";
import {
  Badge,
  Card,
  CardHeader,
  Chip,
  DataGap,
  EmptyState,
  RecordLine,
  Sacko,
  Skeleton,
  Stat,
  Trophy,
} from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { num, ordinal, pct, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

import { ManagerStory, type OwnerStoryData } from "./ManagerStory";

type OwnerSeasonRow = components["schemas"]["OwnerSeasonRow"];
type RivalryMatrix = components["schemas"]["RivalryMatrix"];
type CommissionerTerm = components["schemas"]["CommissionerTerm"];

async function fetchCareer(id: number) {
  const { data, error } = await api.GET("/v1/owners/{owner_id}", {
    params: { path: { owner_id: id } },
  });
  if (error || !data) throw new Error("not_found");
  return data.data;
}

async function fetchSeasons(id: number) {
  const { data, error } = await api.GET("/v1/owners/{owner_id}/seasons", {
    params: { path: { owner_id: id } },
  });
  if (error || !data) throw new Error("Failed to load seasons");
  return data.data.seasons;
}

async function fetchTrajectory(id: number) {
  const { data, error } = await api.GET("/v1/owners/{owner_id}/trajectory", {
    params: { path: { owner_id: id } },
  });
  if (error || !data) throw new Error("Failed to load trajectory");
  return data.data.points;
}

async function fetchRivalryMatrix() {
  const { data, error } = await api.GET("/v1/owners/rivalry-matrix");
  if (error || !data) throw new Error("Failed to load rivalries");
  return data.data;
}

async function fetchStory(id: number) {
  const { data, error } = await api.GET("/v1/owners/{owner_id}/story", {
    params: { path: { owner_id: id } },
  });
  if (error || !data) throw new Error("Failed to load story");
  return data.data as OwnerStoryData;
}

/** A scored season always books points; a record-only (pre-coverage) season comes
 *  back with 0 PF. Treat the 0 as an honest gap, never a real total. */
function scored(row: OwnerSeasonRow): boolean {
  return row.points_for > 0;
}

function SeasonRow({ row }: { row: OwnerSeasonRow }) {
  return (
    <tr>
      <td className="num text-faint">{row.season_year ?? "—"}</td>
      <td>
        <Link to={`/teams/${row.team_id}`} className="hover:text-accent">
          <Chip name={row.team_name} avatarUrl={teamAvatarUrl(row.team_id)} />
        </Link>
      </td>
      <td className="dz-num">
        <RecordLine wins={row.wins} losses={row.losses} ties={row.ties} />
      </td>
      <td className="dz-num num">{scored(row) ? num(row.points_for) : <DataGap reason="season_unscored" size="sm" />}</td>
      <td className="dz-num num">{ordinal(row.final_rank)}</td>
      <td className="dz-num">
        {row.is_champion ? (
          <Trophy label="Champion" />
        ) : row.is_sacko ? (
          <Sacko />
        ) : row.made_playoffs ? (
          <Badge>playoffs</Badge>
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}

/** The owner's row of the rivalry matrix, split into who they beat up on and who
 *  owns them. Deep-links to the existing pairwise pages. */
function RivalrySnapshot({ ownerId, matrix }: { ownerId: number; matrix: RivalryMatrix }) {
  const nameOf = new Map(matrix.owners.map((o) => [o.owner_id, o.display_name]));
  const rivals = matrix.cells
    .filter((c) => c.a === ownerId && c.b !== ownerId && c.a_win_pct != null && c.games > 0)
    .sort((x, y) => (y.a_win_pct ?? 0) - (x.a_win_pct ?? 0));

  if (rivals.length === 0) {
    return <EmptyState title="No head-to-head history" hint="This manager hasn't met another owner in a scored game yet." />;
  }
  const best = rivals.slice(0, 3);
  const worst = rivals.slice(-3).reverse().filter((c) => !best.includes(c));

  const Line = ({ b, winPct, games }: { b: number; winPct: number; games: number }) => (
    <Link
      to={`/rivalries/${ownerId}/vs/${b}`}
      className="flex items-center justify-between gap-3 rounded-[var(--radius-sm)] px-3 py-2 hover:bg-[var(--surface-2)]"
    >
      <Chip name={nameOf.get(b) ?? `#${b}`} />
      <span className="num text-[var(--fs-sm)] text-muted">
        {pct(winPct)} <span className="text-faint">· {games} GP</span>
      </span>
    </Link>
  );

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div>
        <div className="dz-eyebrow mb-2">Owns</div>
        <div className="space-y-1">
          {best.map((c) => (
            <Line key={c.b} b={c.b} winPct={c.a_win_pct as number} games={c.games} />
          ))}
        </div>
      </div>
      {worst.length > 0 && (
        <div>
          <div className="dz-eyebrow mb-2">Owned by</div>
          <div className="space-y-1">
            {worst.map((c) => (
              <Line key={c.b} b={c.b} winPct={c.a_win_pct as number} games={c.games} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CommissionerCard({ terms }: { terms: CommissionerTerm[] }) {
  if (terms.length === 0) return null;
  const totalSeasons = terms.reduce((sum, t) => sum + t.seasons, 0);
  const isCurrent = terms.some((t) => t.to_year === null || t.to_year === undefined);
  return (
    <Card>
      <CardHeader eyebrow="league service" title="Commissioner" />
      <div className="p-5 space-y-3">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
          <Stat label="Terms" value={terms.length} />
          <Stat label="Seasons served" value={totalSeasons} tone="accent" />
          {isCurrent && (
            <div>
              <div className="dz-eyebrow mb-1">Status</div>
              <span className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-2)] px-2.5 py-1 text-[var(--fs-xs)] font-semibold text-accent">
                Current commissioner
              </span>
            </div>
          )}
        </div>
        <div className="space-y-1">
          {terms.map((t) => (
            <div
              key={`${t.from_year}`}
              className="flex items-center justify-between rounded-[var(--radius-sm)] border border-[var(--hairline)] px-3 py-2"
            >
              <span className="text-[var(--fs-sm)] tabular-nums text-muted">
                {t.from_year}–{t.to_year ?? "present"}
              </span>
              <span className="text-[var(--fs-xs)] text-faint">
                {t.seasons} {t.seasons === 1 ? "season" : "seasons"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

export function ManagerProfilePage() {
  const params = useParams();
  const ownerId = Number(params.ownerId);
  const enabled = Number.isFinite(ownerId);

  const career = useQuery({ queryKey: qk.owner(ownerId), queryFn: () => fetchCareer(ownerId), enabled });
  const seasons = useQuery({ queryKey: qk.ownerSeasons(ownerId), queryFn: () => fetchSeasons(ownerId), enabled });
  const trajectory = useQuery({ queryKey: qk.ownerTrajectory(ownerId), queryFn: () => fetchTrajectory(ownerId), enabled });
  const matrix = useQuery({ queryKey: qk.rivalryMatrix, queryFn: fetchRivalryMatrix, enabled });
  const story = useQuery({ queryKey: qk.ownerStory(ownerId), queryFn: () => fetchStory(ownerId), enabled });

  if (career.isError) {
    return (
      <div className="dz-rise">
        <EmptyState title="Manager not found" hint="No manager exists for this link." />
        <div className="mt-4 text-center">
          <Link to="/managers" className="text-accent hover:underline">
            ← All managers
          </Link>
        </div>
      </div>
    );
  }

  const c = career.data;
  const years = (seasons.data ?? []).map((s) => s.season_year).filter((y): y is number => y != null);
  const span = years.length > 0 ? `${Math.min(...years)}–${Math.max(...years)}` : null;
  const latestSeason = [...(seasons.data ?? [])]
    .filter((s) => s.team_id != null && s.season_year != null)
    .sort((a, b) => Number(b.season_year) - Number(a.season_year))[0];

  // Trajectory is final rank per season (record-only seasons still have a rank),
  // drawn 1-on-top. Domain is the deepest finish on record, min 8 so a small
  // league doesn't crush the axis.
  const points = (trajectory.data ?? []).filter((p) => p.final_rank != null);
  const flowData = points.map((p) => ({ year: String(p.season_year ?? ""), finish: p.final_rank ?? null }));
  const teamCount = Math.max(8, ...points.map((p) => p.final_rank ?? 0));

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Manager{span ? ` · ${span}` : ""}</div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">{c?.display_name ?? "—"}</h1>
          {c && c.championships > 0 && <Trophy label="Champion" count={c.championships} />}
          {c && c.sackos > 0 && <Sacko count={c.sackos} />}
          {latestSeason && (
            <Link to={`/teams/${latestSeason.team_id}`} className="text-muted hover:text-accent">
              Latest roster ({latestSeason.season_year})
            </Link>
          )}
        </div>
      </div>

      {career.isLoading && <Skeleton className="h-40 w-full" />}

      {story.isLoading && <Skeleton className="h-40 w-full" />}
      {story.data && <ManagerStory story={story.data} />}

      {c && (
        <Card className="p-5">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-7">
            <Stat label="Seasons" value={c.seasons_played} />
            <div>
              <div className="dz-eyebrow mb-1">Record</div>
              <div className="mt-1.5">
                <RecordLine wins={c.total_wins} losses={c.total_losses} ties={c.total_ties} />
              </div>
            </div>
            <Stat
              label="Win %"
              value={pct(
                c.total_wins + c.total_losses + c.total_ties > 0
                  ? c.total_wins / (c.total_wins + c.total_losses + c.total_ties)
                  : null,
              )}
              tone="accent"
            />
            <Stat label="Points for" value={num(c.total_points_for, 0)} />
            <Stat label="Best finish" value={ordinal(c.best_finish)} />
            <Stat label="Titles" value={c.championships} unit="★" tone="accent" />
            <Stat label="Sackos" value={c.sackos} unit="💩" />
          </div>
        </Card>
      )}

      {c && c.trophy_case.length > 0 && (
        <Card>
          <CardHeader eyebrow="trophy case" title="Hardware" />
          <div className="flex gap-3 overflow-x-auto p-5">
            {c.trophy_case.map((t, i) => (
              <div key={i} className={`dz-card min-w-[150px] shrink-0 p-3 ${t.is_champion ? "dz-card--hover" : ""}`}>
                <div className="num text-[var(--fs-sm)] text-faint">{t.season_year ?? "—"}</div>
                <div className="mt-1 flex items-center gap-1.5">
                  {t.is_champion ? (
                    <Trophy label="Champion" />
                  ) : t.is_sacko ? (
                    <Sacko />
                  ) : (
                    <span className="num text-accent">{ordinal(t.finish)}</span>
                  )}
                  <span className="truncate font-semibold text-text">{t.team_name ?? "—"}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {c?.consistency && (
        <Card>
          <CardHeader eyebrow="weekly scoring profile" title="Consistency" />
          <div className="grid grid-cols-2 gap-5 p-5 sm:grid-cols-4">
            {c.consistency.available ? (
              <>
                <Stat
                  label="Weekly stdev"
                  value={num(c.consistency.weekly_points_stdev, 1)}
                  tone="accent"
                />
                <Stat label="Consistency rank" value={ordinal(c.consistency.rank_among_owners)} />
                <Stat
                  label="Best season"
                  value={c.consistency.best_season_year ?? "—"}
                  unit={
                    c.consistency.best_season_points_for != null
                      ? `${num(c.consistency.best_season_points_for, 0)} PF`
                      : undefined
                  }
                />
                <Stat label="Signature" value={c.consistency.signature ?? "—"} />
              </>
            ) : (
              <DataGap reason={c.consistency.reason ?? "no_scored_data"} />
            )}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader eyebrow="finish by season" title="Career Trajectory" />
        <div className="p-5">
          {trajectory.isLoading && <Skeleton className="h-[240px] w-full" />}
          {trajectory.data &&
            (flowData.length > 1 ? (
              <RankFlow
                title="Final finish by season (1 = best)"
                data={flowData}
                series={[{ key: "finish", label: "Finish" }]}
                xKey="year"
                xLabel="Season"
                teamCount={teamCount}
              />
            ) : (
              <EmptyState title="Not enough seasons" hint="A trajectory needs at least two seasons on record." />
            ))}
        </div>
      </Card>

      <Card>
        <CardHeader eyebrow="every season" title="Season by Season" />
        <div className="overflow-x-auto p-1">
          {seasons.isLoading && <Skeleton className="m-4 h-40 w-full" />}
          {seasons.data && seasons.data.length > 0 && (
            <table className="dz-table w-full">
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Team</th>
                  <th className="dz-num">Record</th>
                  <th className="dz-num">Points For</th>
                  <th className="dz-num">Finish</th>
                  <th className="dz-num">Result</th>
                </tr>
              </thead>
              <tbody>
                {seasons.data.map((row) => (
                  <SeasonRow key={row.team_id} row={row} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {c && (c.commissioner_terms?.length ?? 0) > 0 && (
        <CommissionerCard terms={c.commissioner_terms!} />
      )}

      <Card>
        <CardHeader eyebrow="head-to-head" title="Rivalries" />
        <div className="p-5">
          {matrix.isLoading && <Skeleton className="h-24 w-full" />}
          {matrix.data && <RivalrySnapshot ownerId={ownerId} matrix={matrix.data} />}
        </div>
      </Card>
    </div>
  );
}
