import { Badge, Chip, RecordLine } from "@/design-system";
import { num, pct, teamAvatarUrl } from "@/lib/format";

import type { PowerRanking } from "./usePower";

/** Movement of the model's rank vs the plain standings rank. Positive = the model
 *  rates the team above its record (a riser); negative = a faller. */
function DeltaTag({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-faint">—</span>;
  const tone = delta > 0 ? "win" : "loss";
  return (
    <Badge variant={tone}>
      {delta > 0 ? `▲ ${delta}` : `▼ ${Math.abs(delta)}`}
    </Badge>
  );
}

/** The power-ranking table + "how this is computed" explainer. Presentational —
 *  shared by the Standings power lens and the Playoffs entry snapshot. */
export function PowerTable({ data }: { data: PowerRanking }) {
  return (
    <>
      <div className="overflow-x-auto">
        <table className="dz-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              <th className="dz-num">Power</th>
              <th className="dz-num">Record</th>
              <th className="dz-num">PF/g</th>
              <th className="dz-num">All-play</th>
              <th className="dz-num">Win%</th>
              <th className="dz-num">Last 3 PF/g</th>
              <th className="dz-num">vs standings</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.team_id}>
                <td className="num text-faint">{r.rank}</td>
                <td>
                  <Chip name={r.team_name ?? r.owner_name} sub={r.owner_name ?? undefined} avatarUrl={teamAvatarUrl(r.team_id)} />
                </td>
                <td className="dz-num font-semibold text-accent">{num(r.power_score)}</td>
                <td className="dz-num">
                  <RecordLine wins={r.wins} losses={r.losses} ties={r.ties} />
                </td>
                <td className="dz-num">{num(r.points_for_per_game)}</td>
                <td className="dz-num text-muted">{pct(r.all_play_win_pct)}</td>
                <td className="dz-num text-muted">{pct(r.win_pct)}</td>
                <td className="dz-num text-muted">{num(r.recent_points_for_per_game)}</td>
                <td className="dz-num">
                  <DeltaTag delta={r.rank_delta} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.explainer && (
        <p className="max-w-prose p-5 pt-3 text-[var(--fs-xs)] text-faint">
          <span className="dz-eyebrow">How this is computed · </span>
          {data.explainer}
        </p>
      )}
    </>
  );
}
