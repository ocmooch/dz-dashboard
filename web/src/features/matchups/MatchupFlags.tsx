import type { components } from "@/lib/api/schema.d.ts";

type MatchupFlag = components["schemas"]["MatchupFlag"];

/** Map a backend flag tone to its CSS modifier. Unknown tones fall back to muted
 *  so a new server-side tone never renders unstyled. */
const TONE_CLASS: Record<string, string> = {
  win: "dz-flag--win",
  loss: "dz-flag--loss",
  accent: "dz-flag--accent",
  warn: "dz-flag--warn",
  muted: "dz-flag--muted",
};

/** A row of superlative flags for a game. Pure presentation — the backend
 *  (analytics/matchup_flags.py) decides which flags apply, their label, tone and
 *  tooltip detail. Renders nothing when there are no flags. */
export function MatchupFlags({
  flags,
  className,
}: {
  flags: MatchupFlag[];
  className?: string;
}) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className={`dz-flags ${className ?? ""}`.trim()}>
      {flags.map((f, i) => (
        <span
          key={`${f.kind}-${f.team_id ?? "x"}-${i}`}
          className={`dz-flag ${TONE_CLASS[f.tone] ?? "dz-flag--muted"}`}
          title={f.detail ?? undefined}
        >
          <span className="dz-flag__dot" aria-hidden="true" />
          {f.label}
        </span>
      ))}
    </div>
  );
}
