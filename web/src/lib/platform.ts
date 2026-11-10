/**
 * Platform provenance + capability copy (Sleeper D1).
 *
 * The ONLY module allowed to name platforms as string literals (enforced by
 * `scripts/check_platform_literals.sh` in CI). Everything else uses the BFF's
 * `platform_label` and these helpers. Copy follows docs/sleeper/03_CROSS_PLATFORM_UX.md §3.
 */
import type { components } from "@/lib/api/schema";

export type Capability = components["schemas"]["Capability"];
export type CapabilityState =
  | "available"
  | "partial"
  | "derived"
  | "not_yet"
  | "not_on_platform"
  | "not_used";

const PLATFORM_LABELS: Record<string, string> = {
  nfl_com: "NFL.com",
  sleeper: "Sleeper",
};

export function platformLabel(platform: string | null | undefined): string {
  if (!platform) return "";
  return PLATFORM_LABELS[platform] ?? platform;
}

/** `03` §3 gap copy, by capability key + the platform lacking it. */
const GAP_COPY: Record<string, Record<string, string>> = {
  lineup_change_log: {
    sleeper: "Lineup-change history isn't available from Sleeper.",
  },
  setting_change_log: {
    sleeper: "Sleeper doesn't publish a settings change log. Current settings are shown.",
  },
  faab_failed_bids: {
    nfl_com: "NFL.com didn't record unsuccessful waiver bids.",
  },
  trades_with_picks_faab: { nfl_com: "NFL.com trades only recorded players." },
};

/** `03` §3 provenance footnotes for derived/computed data. */
const PROVENANCE_COPY: Record<string, Record<string, string>> = {
  official_brackets: {
    nfl_com: "Bracket derived from NFL.com playoff results.",
  },
  potential_points: { nfl_com: "Potential points computed by this dashboard." },
};

const NOT_YET_COPY = "Not available until this week is final.";

function humanize(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Whether a capability renders at all. `not_used` renders nothing (user rule, `00` §3). */
export function isRendered(cap: Capability | null | undefined): boolean {
  return cap != null && cap.state !== "not_used";
}

/** Whether the data is there to show (possibly partial or derived). */
export function isShowable(cap: Capability | null | undefined): boolean {
  return cap != null && ["available", "partial", "derived"].includes(cap.state);
}

/** The one-line gap text for a capability that isn't showable. The BFF note wins. */
export function capabilityGapText(
  key: string,
  cap: Capability | null | undefined,
  platform: string | null | undefined,
): string {
  if (cap?.note) return cap.note;
  if (cap?.state === "not_yet") return NOT_YET_COPY;
  const byPlatform = platform ? GAP_COPY[key]?.[platform] : undefined;
  if (byPlatform) return byPlatform;
  const label = platformLabel(platform);
  return label ? `${humanize(key)} isn't available from ${label}.` : `${humanize(key)} isn't available.`;
}

/** A footnote for derived/computed data, or null when none applies. */
export function provenanceText(key: string, platform: string | null | undefined): string | null {
  return (platform && PROVENANCE_COPY[key]?.[platform]) || null;
}

/** Short state label for tables (About's capability matrix). `not_used` is blank. */
export function capabilityStateLabel(state: string): string {
  const labels: Record<string, string> = {
    available: "Yes",
    partial: "Partial",
    derived: "Derived",
    not_yet: "Not yet",
    not_on_platform: "Not on platform",
    not_used: "",
  };
  return labels[state] ?? state;
}

/** Box-score footnote: where official player points come from (Sleeper D3). */
export function officialPointsNote(source: string | null | undefined): string | null {
  const label = platformLabel(source);
  return label ? `Official player points from ${label}.` : null;
}

/** Box-score note for a commissioner override: the platform's computed score vs the awarded one.
 *  Scores arrive pre-formatted; this module only owns the wording. */
export function commissionerOverrideNote(
  source: string | null | undefined,
  official: string,
  awarded: string,
): string {
  const label = platformLabel(source) || "The platform";
  return `Commissioner override: ${label} scored this team ${official}; the commissioner awarded ${awarded}, which is the league score.`;
}

type PickRef = { season?: number; round?: number };

/** Team-transaction text for the pick/FAAB side of a trade (a player-less leg). */
export function tradeAssetsText(assets: {
  picks_in?: PickRef[];
  picks_out?: PickRef[];
  faab_in?: number;
  faab_out?: number;
}): string {
  const pick = (p: PickRef) => `${p.season ?? "?"} round ${p.round ?? "?"} pick`;
  const parts: string[] = [];
  for (const p of assets.picks_in ?? []) parts.push(`received ${pick(p)}`);
  for (const p of assets.picks_out ?? []) parts.push(`sent ${pick(p)}`);
  if (assets.faab_in) parts.push(`received $${assets.faab_in} FAAB`);
  if (assets.faab_out) parts.push(`sent $${assets.faab_out} FAAB`);
  return parts.length ? `Draft pick / FAAB: ${parts.join(", ")}` : "Draft pick / FAAB";
}

/** Roster slot hint for a Sleeper week with no archived IR list (`slot_note` "bench_or_reserve"). */
export function slotNoteText(note: string | null | undefined): string | null {
  return note === "bench_or_reserve" ? "Bench or reserve: this week's IR list wasn't archived." : null;
}

// ── Cross-era aggregation (Sleeper D4) ──────────────────────────────────────

export type AggregationNote = components["schemas"]["AggregationNote"];
export type ScoringEra = components["schemas"]["ScoringEra"];

function partialPhrase(p: { season_year: number; through_week: number }): string {
  return p.through_week > 0
    ? `${p.season_year} through week ${p.through_week}`
    : `${p.season_year} (no week final yet)`;
}

/** One line under a cross-season card: what was partly counted or left out. `null` renders nothing. */
export function aggregationNoteText(note: AggregationNote | null | undefined): string | null {
  if (!note) return null;
  const partial = (note.partial_seasons ?? []).map(partialPhrase).join(", ");
  const excluded = (note.excluded_seasons ?? []).join(", ");
  if (note.reason === "season_totals_exclude_in_progress") {
    if (partial && excluded)
      return `Single-game records include ${partial}. Season totals leave out ${excluded} (in progress).`;
    if (excluded) return `Season totals leave out ${excluded} (in progress).`;
  }
  if (partial) return `Includes ${partial} (in progress; subject to change).`;
  if (excluded) return `Leaves out ${excluded}.`;
  return null;
}

/** Neutral rules-era chip text ("2011–2025 scoring"), only when the league spans > 1 era. */
export function scoringEraText(
  era: ScoringEra | null | undefined,
  eraCount: number | null | undefined,
): string | null {
  if (!era || (eraCount ?? 0) < 2) return null;
  return `${era.label} scoring`;
}

const DRAFT_TYPE_LABELS: Record<string, string> = {
  snake: "Snake draft",
  auction: "Auction draft",
  linear: "Linear draft",
};

/** Draft-board label for the stored draft type; `null` (nothing shown) when unknown. */
export function draftTypeLabel(type: string | null | undefined): string | null {
  return type ? (DRAFT_TYPE_LABELS[type] ?? null) : null;
}
