// TanStack Query key factory — one place so caches dedupe and invalidate cleanly.
export const qk = {
  meta: ["meta"] as const,
  seasons: ["seasons"] as const,
  standings: (seasonId: number) => ["standings", seasonId] as const,
  owners: ["owners"] as const,
  rivalryMatrix: ["owners", "rivalry-matrix"] as const,
  headToHead: (a: number, b: number) => ["owners", "head-to-head", a, b] as const,
  records: ["records"] as const,
  championships: ["records", "championships"] as const,
  weekMatchups: (seasonId: number, week: number) => ["matchups", seasonId, week] as const,
  boxScore: (matchupId: number) => ["box-score", matchupId] as const,
};
