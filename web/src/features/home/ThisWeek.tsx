import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  AWAITING_FINAL_LABEL,
  Badge,
  Card,
  CardHeader,
  Chip,
  EraMarker,
  RecordLine,
  throughWeekText,
} from "@/design-system";
import { GameCardView } from "@/features/matchups/MatchupsPage";
import { fetchCurrentSeason } from "@/lib/currentSeason";
import { num, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

/** Home's in-season command center (Sleeper D3): the last final week's results, the unfinished
 *  week's pairings (unscored, "awaiting final"), and the top of the standings. Renders nothing
 *  off-season (`available: false`). All weeks and records come from `/v1/seasons/current`. */
export function ThisWeek() {
  const { data } = useQuery({ queryKey: qk.currentSeason, queryFn: fetchCurrentSeason });
  if (!data?.available) return null;
  const qualifier = throughWeekText(data.last_finalized_week, data.pending_week);

  return (
    <Card>
      <CardHeader
        eyebrow={`season ${data.season_year ?? ""}${qualifier ? ` · ${qualifier}` : ""}`}
        title="This week"
        action={<EraMarker label={data.platform_label} />}
      />
      <div className="grid grid-cols-1 gap-6 p-5 lg:grid-cols-3">
        <section className="space-y-3 lg:col-span-2">
          {data.pending_week != null && data.pending_pairings.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-2">
                <h3 className="dz-eyebrow">Week {data.pending_week}</h3>
                <Badge variant="gap">{AWAITING_FINAL_LABEL}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {data.pending_pairings.map((g) => (
                  <GameCardView key={g.matchup_id} game={g} />
                ))}
              </div>
            </div>
          )}
          {data.last_finalized_week != null && data.latest_results.length > 0 && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="dz-eyebrow">Week {data.last_finalized_week} results</h3>
                <Link to={`/matchups?week=${data.last_finalized_week}`} className="dz-badge dz-badge--accent">
                  All matchups →
                </Link>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {data.latest_results.map((g) => (
                  <GameCardView key={g.matchup_id} game={g} />
                ))}
              </div>
            </div>
          )}
        </section>
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="dz-eyebrow">Standings</h3>
            <Link to="/standings" className="dz-badge dz-badge--accent">
              Full table →
            </Link>
          </div>
          <table className="dz-table">
            <tbody>
              {data.standings_top.map((r) => (
                <tr key={r.team_id}>
                  <td className="num text-faint">{r.rank}</td>
                  <td>
                    <Chip
                      name={r.team_name ?? r.owner_name}
                      sub={r.owner_name ?? undefined}
                      avatarUrl={teamAvatarUrl(r.team_id)}
                    />
                  </td>
                  <td className="dz-num">
                    <RecordLine wins={r.wins} losses={r.losses} ties={r.ties} />
                  </td>
                  <td className="dz-num">{num(r.points_for)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </Card>
  );
}
