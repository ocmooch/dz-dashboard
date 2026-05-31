import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, Skeleton } from "@/design-system";
import { BarCompare } from "@/charts";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type Board = Awaited<ReturnType<typeof fetchBoard>>;
type Pick = Board["rounds"][number]["picks"][number];

async function fetchBoard(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/draft", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load draft board");
  return data.data;
}

async function fetchValue(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/draft/value", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load draft value");
  return data.data;
}

/** Signed value with steal/bust colouring. A positive value beat its slot. */
function ValueTag({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const tone = value > 0 ? "win" : value < 0 ? "loss" : "default";
  return (
    <Badge variant={tone}>
      {value > 0 ? "+" : ""}
      {num(value)}
    </Badge>
  );
}

function PickCell({ pick }: { pick: Pick }) {
  return (
    <Link
      to={pick.player_id != null ? `/players/${pick.player_id}` : "#"}
      className="block rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-1)] p-3 transition-colors hover:border-[var(--accent)]"
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="num text-[var(--fs-xs)] text-faint">#{pick.overall}</span>
        {pick.available ? <ValueTag value={pick.value} /> : <DataGap reason={pick.reason ?? undefined} size="sm" />}
      </div>
      <div className="font-semibold text-text">{pick.player_name ?? "—"}</div>
      <div className="flex items-center justify-between text-[var(--fs-xs)] text-muted">
        <span>{pick.position ?? "—"}</span>
        <span className="num">{pick.season_points != null ? `${num(pick.season_points)} pts` : "—"}</span>
      </div>
      <div className="mt-2 border-t border-[var(--hairline)] pt-2">
        <Chip name={pick.owner_name} sub={pick.team_name ?? undefined} />
      </div>
    </Link>
  );
}

/** A steal/bust leaderboard row, deep-linking to the drafted player. */
function PickLine({ pick, rank }: { pick: Pick; rank: number }) {
  return (
    <Link
      to={pick.player_id != null ? `/players/${pick.player_id}` : "#"}
      className="flex items-center justify-between gap-3 rounded-[var(--radius-sm)] px-2 py-1.5 hover:bg-[var(--surface-1)]"
    >
      <span className="flex items-center gap-2 truncate">
        <span className="num w-4 text-[var(--fs-xs)] text-faint">{rank}</span>
        <span className="truncate font-medium text-text">{pick.player_name ?? "—"}</span>
        <span className="text-[var(--fs-xs)] text-faint">
          #{pick.overall} · {pick.owner_name ?? "—"}
        </span>
      </span>
      <ValueTag value={pick.value} />
    </Link>
  );
}

export function DraftPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;

  const board = useQuery({
    queryKey: seasonId ? qk.draftBoard(seasonId) : ["draft", "none"],
    queryFn: () => fetchBoard(seasonId as number),
    enabled: seasonId != null,
  });
  const value = useQuery({
    queryKey: seasonId ? qk.draftValue(seasonId) : ["draft", "none", "value"],
    queryFn: () => fetchValue(seasonId as number),
    enabled: seasonId != null && board.data?.available === true,
  });

  const chartRows =
    value.data?.picks
      ?.filter((p) => p.value != null)
      .map((p) => ({
        label: `#${p.overall} ${(p.player_name ?? "").split(" ").slice(-1)[0]}`,
        value: p.value as number,
      })) ?? [];

  return (
    <div className="dz-rise space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Draft</h1>
        </div>
      </div>

      {board.isLoading && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}
      {board.isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => board.refetch()} />
      )}

      {board.data && !board.data.available && (
        <Card>
          <CardHeader eyebrow={`season ${board.data.season_year}`} title="Draft board" />
          <div className="space-y-3 p-5">
            <DataGap reason={board.data.reason ?? undefined} />
            <p className="max-w-prose text-[var(--fs-sm)] text-muted">
              The Phase 1 reconstruction didn&rsquo;t capture this league&rsquo;s draft, so there
              are no picks to show. Rather than invent a board, the dashboard says so plainly.
            </p>
          </div>
        </Card>
      )}

      {board.data?.available && (
        <>
          {value.data?.available && (value.data.steals.length > 0 || value.data.busts.length > 0) && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader eyebrow="outperformed their slot" title="Steals" />
                <div className="space-y-1 p-3">
                  {value.data.steals.length === 0 && (
                    <p className="px-2 py-1.5 text-[var(--fs-sm)] text-faint">No clear steals.</p>
                  )}
                  {value.data.steals.map((p, i) => (
                    <PickLine key={p.overall} pick={p} rank={i + 1} />
                  ))}
                </div>
              </Card>
              <Card>
                <CardHeader eyebrow="fell short of their slot" title="Busts" />
                <div className="space-y-1 p-3">
                  {value.data.busts.length === 0 && (
                    <p className="px-2 py-1.5 text-[var(--fs-sm)] text-faint">No clear busts.</p>
                  )}
                  {value.data.busts.map((p, i) => (
                    <PickLine key={p.overall} pick={p} rank={i + 1} />
                  ))}
                </div>
              </Card>
            </div>
          )}

          {chartRows.length > 0 && (
            <Card>
              <CardHeader eyebrow="points above / below slot expectation" title="Pick value" />
              <div className="p-5">
                <BarCompare
                  title="Draft pick value by overall pick"
                  data={chartRows}
                  series={[{ key: "value", label: "Value (pts)" }]}
                  xKey="label"
                  xLabel="Pick"
                  height={220}
                />
                {value.data?.definition && (
                  <p className="mt-3 max-w-prose text-[var(--fs-xs)] text-faint">
                    {value.data.definition}
                  </p>
                )}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader
              eyebrow={`${board.data.num_teams ?? "—"} teams`}
              title="Draft board"
            />
            <div className="space-y-5 p-5">
              {board.data.rounds.map((rnd) => (
                <div key={rnd.round}>
                  <div className="dz-eyebrow mb-2">Round {rnd.round}</div>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
                    {rnd.picks.map((p) => (
                      <PickCell key={p.overall} pick={p} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
