// TanStack Query key factory — one place so caches dedupe and invalidate cleanly.
export const qk = {
  meta: ["meta"] as const,
  seasons: ["seasons"] as const,
  standings: (seasonId: number) => ["standings", seasonId] as const,
  owners: ["owners"] as const,
  rivalryMatrix: ["owners", "rivalry-matrix"] as const,
  records: ["records"] as const,
};
