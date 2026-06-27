import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { type ChartRow, type SeriesDef, Beeswarm, LegacySpine, MetricScatter, StreamArea } from "@/charts";
import { Card, CardHeader, EmptyState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

// The Viz Lab is a deliberate holding space: new data-visualization components
// live here against real data while they prove out, before they settle into (or
// reshape) the dashboard's permanent structure. Each exhibit is self-contained so
// adding the next spun-out viz is just another <Exhibit>.

async function fetchOwners() {
  const { data, error } = await api.GET("/v1/owners");
  if (error || !data) throw new Error("Failed to load owners");
  return data.data.owners;
}

async function fetchSeasons(id: number) {
  const { data, error } = await api.GET("/v1/owners/{owner_id}/seasons", {
    params: { path: { owner_id: id } },
  });
  if (error || !data) throw new Error("Failed to load seasons");
  return data.data.seasons;
}

async function fetchTeams() {
  const { data, error } = await api.GET("/v1/teams");
  if (error || !data) throw new Error("Failed to load teams");
  return data.data.teams;
}

async function fetchSeasonList() {
  const { data, error } = await api.GET("/v1/seasons");
  if (error || !data) throw new Error("Failed to load seasons");
  return data.data.seasons;
}

async function fetchWeeklyScores(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/weekly-scores", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load weekly scores");
  return data.data;
}

async function fetchEfficiency(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/efficiency", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load efficiency");
  return data.data;
}

type TeamRow = { owner_id: number; owner_name?: string | null; season_year?: number | null; points_for: number };

/** Cumulative league points by manager across seasons → StreamArea rows. Limited to
 *  the top-N all-time scorers so the bands stay readable; pure presentation. */
function buildCumulativePoints(rows: TeamRow[], topN = 8): { data: ChartRow[]; series: SeriesDef[] } {
  const totals = new Map<number, { name: string; total: number }>();
  for (const r of rows) {
    if (r.season_year == null) continue;
    const o = totals.get(r.owner_id) ?? { name: r.owner_name ?? `#${r.owner_id}`, total: 0 };
    o.total += r.points_for ?? 0;
    totals.set(r.owner_id, o);
  }
  const top = [...totals.entries()].sort((a, b) => b[1].total - a[1].total).slice(0, topN).map(([id]) => id);
  const years = [...new Set(rows.map((r) => r.season_year).filter((y): y is number => y != null))].sort((a, b) => a - b);
  const running = new Map<number, number>();
  const data: ChartRow[] = years.map((y) => {
    const row: ChartRow = { year: String(y) };
    for (const id of top) {
      const yearPts = rows
        .filter((r) => r.owner_id === id && r.season_year === y)
        .reduce((s, r) => s + (r.points_for ?? 0), 0);
      running.set(id, (running.get(id) ?? 0) + yearPts);
      row[String(id)] = Math.round(running.get(id) ?? 0);
    }
    return row;
  });
  const series: SeriesDef[] = top.map((id) => ({ key: String(id), label: totals.get(id)?.name ?? `#${id}` }));
  return { data, series };
}

/** Exhibit 2 — cumulative league points by manager (dynasty stream). */
function DynastyStreamExhibit() {
  const teams = useQuery({ queryKey: qk.teams, queryFn: fetchTeams });
  const stream = teams.data ? buildCumulativePoints(teams.data) : null;
  return (
    <Exhibit
      title="Dynasty Stream"
      blurb="Cumulative league points by manager across every season — band thickness reads as dominance, and a dynasty is a band that swells. Top-8 all-time scorers shown."
      home="Timeline (eras / dynasties) — or here while it settles."
    >
      {teams.isLoading ? (
        <Skeleton className="h-[300px] w-full" />
      ) : stream && stream.data.length > 1 ? (
        <StreamArea
          title="Cumulative league points by manager"
          data={stream.data}
          series={stream.series}
          xKey="year"
          xLabel="Season"
          height={320}
        />
      ) : (
        <EmptyState title="Not enough history" hint="Need at least two seasons of team scoring." />
      )}
    </Exhibit>
  );
}

function Exhibit({
  title,
  blurb,
  home,
  controls,
  children,
}: {
  title: string;
  blurb: string;
  home: string;
  controls?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader eyebrow="exhibit" title={title} action={controls} />
      <div className="space-y-4 p-5">
        <p className="max-w-2xl text-[var(--fs-sm)] text-muted">{blurb}</p>
        {children}
        <p className="text-[var(--fs-xs)] text-faint">Natural home: {home}</p>
      </div>
    </Card>
  );
}

/** Exhibit 1 — the Career Legacy Spine, previewed against a chosen manager. */
function LegacySpineExhibit() {
  const owners = useQuery({ queryKey: qk.owners, queryFn: fetchOwners });
  const [picked, setPicked] = useState<number | null>(null);

  // Default to the longest-tenured manager — the richest spine to look at first.
  const sorted = [...(owners.data ?? [])].sort((a, b) => b.seasons_played - a.seasons_played);
  const ownerId = picked ?? sorted[0]?.owner_id ?? null;

  const seasons = useQuery({
    queryKey: qk.ownerSeasons(ownerId ?? -1),
    queryFn: () => fetchSeasons(ownerId as number),
    enabled: ownerId != null,
  });

  const spineSeasons = [...(seasons.data ?? [])]
    .filter((s) => s.season_year != null)
    .sort((a, b) => Number(a.season_year) - Number(b.season_year))
    .map((s) => ({
      season_year: s.season_year ?? null,
      final_rank: s.final_rank ?? null,
      is_champion: s.is_champion ?? false,
      is_sacko: s.is_sacko ?? false,
    }));
  const ranked = spineSeasons.filter((s) => s.final_rank != null).length;

  const picker = (
    <label className="flex items-center gap-2 text-[var(--fs-sm)] text-muted">
      <span className="dz-eyebrow">Manager</span>
      <select
        aria-label="Manager"
        className="dz-season-select"
        value={ownerId ?? ""}
        onChange={(e) => setPicked(Number(e.target.value))}
      >
        {sorted.map((o) => (
          <option key={o.owner_id} value={o.owner_id}>
            {o.display_name ?? `#${o.owner_id}`} · {o.seasons_played} seasons
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <Exhibit
      title="Career Legacy Spine"
      blurb="A manager's final finish across every season (rank 1 on top), with gold = championship and red = Sacko. One image = a career — peaks are titles, the floor is the Sacko."
      home="Manager profile (already live there)."
      controls={owners.data ? picker : undefined}
    >
      {owners.isLoading || seasons.isLoading ? (
        <Skeleton className="h-[260px] w-full" />
      ) : ranked > 1 ? (
        <LegacySpine
          title="Final finish by season (1 = best · gold = title · red = Sacko)"
          seasons={spineSeasons}
          height={260}
        />
      ) : (
        <EmptyState title="Not enough seasons" hint="Pick a manager with at least two ranked seasons." />
      )}
    </Exhibit>
  );
}

/** Exhibit 3 — weekly-score beeswarm (boom/bust spread) for a chosen season. */
function WeeklyBeeswarmExhibit() {
  const seasons = useQuery({ queryKey: qk.seasons, queryFn: fetchSeasonList });
  const [picked, setPicked] = useState<number | null>(null);

  // Default to the latest scored season — the richest spread to look at first.
  const scored = (seasons.data ?? []).filter((s) => s.is_scored);
  const seasonId = picked ?? scored[scored.length - 1]?.season_id ?? null;

  const weekly = useQuery({
    queryKey: ["weekly-scores", seasonId ?? -1],
    queryFn: () => fetchWeeklyScores(seasonId as number),
    enabled: seasonId != null,
  });

  const groups = (weekly.data?.teams ?? []).map((t) => ({
    label: t.team_name ?? t.owner_name ?? `#${t.team_id}`,
    values: t.scores.filter((s) => !s.is_playoff && s.score != null).map((s) => s.score as number),
  }));

  const picker = (
    <label className="flex items-center gap-2 text-[var(--fs-sm)] text-muted">
      <span className="dz-eyebrow">Season</span>
      <select
        aria-label="Season"
        className="dz-season-select"
        value={seasonId ?? ""}
        onChange={(e) => setPicked(Number(e.target.value))}
      >
        {scored.map((s) => (
          <option key={s.season_id} value={s.season_id}>
            {s.season_year}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <Exhibit
      title="Weekly Scoring Beeswarm"
      blurb="Every team's weekly scores for a season, one strip each — a tight cluster is a steady manager, a wide scatter is boom/bust. Regular-season weeks only."
      home="A season view / Stats — or here while it settles."
      controls={seasons.data ? picker : undefined}
    >
      {seasons.isLoading || weekly.isLoading ? (
        <Skeleton className="h-[300px] w-full" />
      ) : groups.some((g) => g.values.length > 0) ? (
        <Beeswarm title="Weekly team scores" xLabel="Fantasy points" groups={groups} />
      ) : (
        <EmptyState title="No weekly scores" hint="This season has no team scores to plot." />
      )}
    </Exhibit>
  );
}

/** Exhibit 4 — manager lineup efficiency vs scoring (Manager IQ) for a season. */
function EfficiencyExhibit() {
  const seasons = useQuery({ queryKey: qk.seasons, queryFn: fetchSeasonList });
  const [picked, setPicked] = useState<number | null>(null);
  const scored = (seasons.data ?? []).filter((s) => s.is_scored);
  const seasonId = picked ?? scored[scored.length - 1]?.season_id ?? null;

  const eff = useQuery({
    queryKey: ["efficiency", seasonId ?? -1],
    queryFn: () => fetchEfficiency(seasonId as number),
    enabled: seasonId != null,
  });

  const teams = eff.data?.teams ?? [];
  const meanEff = teams.length ? teams.reduce((s, t) => s + t.efficiency_pct, 0) / teams.length : 0;
  const meanPf = teams.length ? teams.reduce((s, t) => s + t.points_for, 0) / teams.length : 0;
  const points = teams.map((t) => ({
    label: t.team_name ?? t.owner_name ?? `#${t.team_id}`,
    x: Math.round((t.efficiency_pct - meanEff) * 1000) / 10, // efficiency pts vs avg
    y: Math.round((t.points_for - meanPf) * 10) / 10,
    note: `${Math.round(t.efficiency_pct * 1000) / 10}% · ${Math.round(t.points_for)} PF`,
  }));

  const picker = (
    <label className="flex items-center gap-2 text-[var(--fs-sm)] text-muted">
      <span className="dz-eyebrow">Season</span>
      <select
        aria-label="Efficiency season"
        className="dz-season-select"
        value={seasonId ?? ""}
        onChange={(e) => setPicked(Number(e.target.value))}
      >
        {scored.map((s) => (
          <option key={s.season_id} value={s.season_id}>
            {s.season_year}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <Exhibit
      title="Manager Efficiency (Lineup IQ)"
      blurb="How much of each team's optimal lineup the manager actually started, vs how much they scored — both relative to the season average. Top-right = sharp and point-rich; bottom-left = leaky and low."
      home="A Managers comparison — or here while it settles."
      controls={seasons.data ? picker : undefined}
    >
      {seasons.isLoading || eff.isLoading ? (
        <Skeleton className="h-[300px] w-full" />
      ) : points.length > 0 ? (
        <MetricScatter
          title="Lineup efficiency vs scoring (relative to season average)"
          xLabel="Efficiency vs avg (pts)"
          yLabel="Points-for vs avg"
          points={points}
        />
      ) : (
        <EmptyState title="No solvable lineups" hint="This season has no full lineups to score efficiency from." />
      )}
    </Exhibit>
  );
}

export function VizLabPage() {
  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Experimental</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Viz Lab</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          A holding space for new data-visualization components while they prove out and find
          their permanent home in the dashboard. Things here will move, change, or graduate.
        </p>
      </div>

      <LegacySpineExhibit />
      <WeeklyBeeswarmExhibit />
      <EfficiencyExhibit />
      <DynastyStreamExhibit />
    </div>
  );
}
