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
  draftBoard: (seasonId: number) => ["draft", seasonId] as const,
  draftValue: (seasonId: number) => ["draft", seasonId, "value"] as const,
  power: (seasonId: number) => ["power", seasonId] as const,
  powerTimeline: (seasonId: number) => ["power", seasonId, "timeline"] as const,
  standingsTimeline: (seasonId: number) => ["standings", seasonId, "timeline"] as const,
  players: (filters: Record<string, unknown>) => ["players", filters] as const,
  player: (playerId: number) => ["player", playerId] as const,
  playerScoring: (playerId: number, season: number) =>
    ["player", playerId, "scoring", season] as const,
  playerOwnership: (playerId: number) => ["player", playerId, "ownership"] as const,
  playerAvailability: (playerId: number, season: number) =>
    ["player", playerId, "availability", season] as const,
  topScorers: (filters: Record<string, unknown>) => ["stats", "top-scorers", filters] as const,
  seasonTotals: (filters: Record<string, unknown>) =>
    ["stats", "season-totals", filters] as const,
  team: (teamId: number) => ["team", teamId] as const,
  teamRoster: (teamId: number, week: number | null) => ["team", teamId, "roster", week] as const,
  teamSchedule: (teamId: number) => ["team", teamId, "schedule"] as const,
  teamScoringTrend: (teamId: number) => ["team", teamId, "scoring-trend"] as const,
  teamTransactions: (teamId: number) => ["team", teamId, "transactions"] as const,
};
