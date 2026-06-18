import type { components } from "@/lib/api/schema";
import { num } from "@/lib/format";

type ScheduleGame = components["schemas"]["ScheduleGame"];

/** A compact horizontal W/L strip — one cell per game in week order. Green for a
 *  win, red for a loss, muted for a tie or an unplayed week. Playoff games are
 *  set apart subtly: a slim divider opens the postseason and those cells carry a
 *  thin ring, so the phase reads as distinct without competing with the results. */
export function ResultTimeline({ games }: { games: ScheduleGame[] }) {
  const firstPlayoffIdx = games.findIndex((g) => g.is_playoff);
  return (
    <div className="flex flex-wrap items-center gap-1">
      {games.map((g, i) => {
        const tone =
          g.result === "W"
            ? "bg-win"
            : g.result === "L"
              ? "bg-loss"
              : "bg-[var(--surface-2)] border border-[var(--hairline)]";
        const opp = g.opponent_team_name ?? g.opponent_owner_name ?? "Bye";
        const score =
          g.team_score != null && g.opponent_score != null
            ? ` · ${num(g.team_score)}–${num(g.opponent_score)}`
            : "";
        const startsPlayoffs = i === firstPlayoffIdx && firstPlayoffIdx > 0;
        return (
          <div key={g.matchup_id} className="flex items-center gap-1">
            {startsPlayoffs && (
              <span
                className="mx-1 self-stretch border-l border-[var(--accent)] pl-1 text-[var(--fs-xs)] uppercase tracking-wide text-faint"
                aria-hidden
              >
                playoffs
              </span>
            )}
            <span
              title={`wk ${g.week} · ${g.result ?? "—"} vs ${opp}${score}`}
              className={[
                "inline-block h-6 w-6 rounded-[var(--radius-sm)]",
                tone,
                g.is_playoff ? "ring-1 ring-inset ring-[color:var(--accent)]" : "",
              ].join(" ")}
            />
          </div>
        );
      })}
    </div>
  );
}
