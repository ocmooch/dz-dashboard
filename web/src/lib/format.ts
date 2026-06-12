// Display-only formatting. No business logic — every number already arrives
// computed from the BFF; we only render it.

export function record(wins: number, losses: number, ties: number): string {
  return ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
}

export function num(value: number | null | undefined, dp = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
}

export function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

export function ordinal(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}

export function initials(name: string | null | undefined): string {
  if (!name) return "··";
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "");
}

/** URL for a team's season logo, streamed by the BFF from Phase 1's asset
 *  store. `<Chip avatarUrl=…>` renders it and falls back to the name monogram
 *  on a missing avatar / 404 (Q11). Returns undefined when there's no team id. */
export function teamAvatarUrl(teamId: number | null | undefined): string | undefined {
  return teamId == null ? undefined : `/v1/teams/${teamId}/avatar`;
}
