// Pivot a per-team timeline (one points[] array per team) into the row-per-week
// shape the RankFlow chart wants, with one numeric column keyed by team_id. Pure
// presentation reshaping — the ranks themselves are computed by the BFF. Shared
// by the standings and power timelines so both bump charts read identically.
import type { ChartRow, SeriesDef } from "@/charts";

type TimelinePoint = { week: number; rank: number };
type TimelineTeam = {
  team_id: number;
  team_name?: string | null;
  owner_name?: string | null;
  points: TimelinePoint[];
};

export type RankFlowData = {
  data: ChartRow[];
  series: SeriesDef[];
  teamCount: number;
};

/** Reshape `{ teams: [{ team_id, owner_name, points: [{week, rank}] }] }` into
 *  RankFlow's `{ data, series, teamCount }`. */
export function toRankFlow(teams: TimelineTeam[]): RankFlowData {
  const series: SeriesDef[] = teams.map((t) => ({
    key: String(t.team_id),
    label: t.owner_name ?? t.team_name ?? `Team ${t.team_id}`,
  }));

  const byWeek = new Map<number, ChartRow>();
  for (const t of teams) {
    for (const p of t.points) {
      const row = byWeek.get(p.week) ?? { week: p.week };
      row[String(t.team_id)] = p.rank;
      byWeek.set(p.week, row);
    }
  }
  const data = [...byWeek.values()].sort((a, b) => Number(a.week) - Number(b.week));
  return { data, series, teamCount: teams.length };
}
