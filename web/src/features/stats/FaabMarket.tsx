import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge, CapabilityGate, Card, CardHeader, Chip, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { pct, teamAvatarUrl } from "@/lib/format";
import { bidMarginText } from "@/lib/platform";
import { qk } from "@/lib/queryKeys";

type BidWar = components["schemas"]["BidWar"];
type TeamRef = components["schemas"]["MarketTeamRef"];

async function fetchFaabMarket(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/faab-market", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load the FAAB market");
  return data.data;
}

const money = (v: number | null | undefined) => (v == null ? "—" : `$${v}`);

function TeamName({ team }: { team: TeamRef }) {
  return (
    <Link to={`/teams/${team.team_id}`} className="hover:text-accent">
      <Chip
        name={team.team_name ?? team.owner_name ?? "—"}
        sub={team.team_name ? (team.owner_name ?? undefined) : undefined}
        avatarUrl={teamAvatarUrl(team.team_id)}
      />
    </Link>
  );
}

function BidWarCard({ war }: { war: BidWar }) {
  const margin = bidMarginText(war.margin);
  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-0)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-semibold text-text">{war.player?.player_name ?? "Unknown player"}</span>
        <span className="dz-eyebrow text-faint">Wk {war.week}</span>
      </div>
      <ol className="space-y-0.5">
        {war.bids.map((b, i) => (
          <li key={i} className="flex items-center justify-between gap-2 text-[var(--fs-sm)]">
            <span className={b.won ? "font-semibold text-win" : "text-muted"}>
              {b.team.team_name ?? b.team.owner_name ?? "—"}
            </span>
            <span className={`num ${b.won ? "font-semibold text-win" : "text-muted"}`}>{money(b.bid)}</span>
          </li>
        ))}
      </ol>
      {margin && <div className="mt-2 text-[var(--fs-xs)] text-faint">{margin}</div>}
    </div>
  );
}

/** The season's FAAB market: spend per team, the biggest bids, and bid wars (Sleeper D6). */
export function FaabMarketView({
  seasonId,
  platform,
}: {
  seasonId: number | undefined;
  platform: string | null | undefined;
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: seasonId ? qk.faabMarket(seasonId) : ["faab-market", "none"],
    queryFn: () => fetchFaabMarket(seasonId as number),
    enabled: seasonId != null,
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError)
    return <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />;
  if (!data) return null;
  if (!data.is_faab_era) {
    return (
      <Card className="p-5">
        <Badge>Waiver priority era</Badge>
        <p className="mt-2 text-[var(--fs-sm)] text-muted">
          This season used waiver priority, not FAAB bids.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader eyebrow={`budget ${money(data.budget)} per team`} title="FAAB spend" />
        <div className="overflow-x-auto">
          <table className="dz-table">
            <thead>
              <tr>
                <th>Team</th>
                <th className="dz-num">Spent</th>
                <th className="dz-num">% of budget</th>
                <th className="dz-num">Won</th>
                <th className="dz-num">Lost</th>
                <th className="dz-num">Largest</th>
              </tr>
            </thead>
            <tbody>
              {data.teams.map((t) => (
                <tr key={t.team.team_id}>
                  <td>
                    <TeamName team={t.team} />
                  </td>
                  <td className="dz-num">{money(t.spent)}</td>
                  <td className="dz-num text-muted">
                    {t.pct_of_budget != null ? pct(t.pct_of_budget) : "—"}
                  </td>
                  <td className="dz-num">{t.winning_bids}</td>
                  <td className="dz-num text-muted">{t.failed_bids ?? "—"}</td>
                  <td className="dz-num text-muted">{money(t.largest_bid)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader eyebrow="winning bids" title="Biggest bids" />
          <ol className="divide-y divide-[var(--hairline)] border-t border-[var(--hairline)]">
            {data.top_bids.map((b, i) => (
              <li key={i} className="flex items-center gap-3 px-5 py-1.5 text-[var(--fs-sm)]">
                <span className="dz-eyebrow w-12 shrink-0 text-faint">Wk {b.week ?? "—"}</span>
                <span className="min-w-0 truncate text-text">
                  {b.player?.player_name ?? "Unknown player"}
                </span>
                <span className="min-w-0 truncate text-muted">{b.team.team_name ?? b.team.owner_name}</span>
                <span className="num ml-auto shrink-0 font-semibold">{money(b.bid)}</span>
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <CardHeader eyebrow="contested claims" title="Bid wars" />
          <CapabilityGate capKey="faab_failed_bids" cap={data.failed_bids_capability} platform={platform}>
            {data.bid_wars.length === 0 ? (
              <p className="px-5 pb-4 text-[var(--fs-sm)] text-faint">No contested claims this season.</p>
            ) : (
              <div className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-2">
                {data.bid_wars.map((w, i) => (
                  <BidWarCard key={i} war={w} />
                ))}
              </div>
            )}
          </CapabilityGate>
        </Card>
      </div>
    </div>
  );
}
