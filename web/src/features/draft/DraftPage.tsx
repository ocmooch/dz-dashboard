import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Button, Card, CardHeader, DataGap, ErrorState, Skeleton, Tabs } from "@/design-system";
import { BarCompare } from "@/charts";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type Board = Awaited<ReturnType<typeof fetchBoard>>;
type Pick = Board["rounds"][number]["picks"][number];
type Lens = "weighted" | "points";
type ChartOrder = "metric" | "draft";

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

/** Tooltip spelling out how a pick's composite impact was built. */
function impactTitle(pick: Pick): string | undefined {
  const c = pick.impact_components;
  if (!c || pick.impact == null) return undefined;
  let t =
    `Impact ${num(pick.impact)} = position-normalized value ${num(c.normalized_value)}` +
    ` (raw ${num(c.base_value)}) × cost ${c.cost_weight.toFixed(2)}`;
  if (c.opportunity_weight !== 1) {
    t += ` × carry ${c.opportunity_weight.toFixed(2)} (${c.bench_weeks} bench / ${c.ir_weeks} IR wks)`;
  } else if (!c.opportunity_available) {
    t += " (carry cost unknown)";
  }
  return t;
}

/** Composite draft-impact badge: the headline ranking number, steal/bust coloured,
 *  with the honest per-slot value shown alongside when the two differ. Falls back
 *  to value when the BFF hasn't supplied an impact (e.g. uncomputable picks). */
function ImpactTag({ pick }: { pick: Pick }) {
  const impact = pick.impact ?? pick.value;
  if (impact == null) return null;
  const tone = impact > 0 ? "win" : impact < 0 ? "loss" : "default";
  const showValue = pick.impact != null && pick.value != null && pick.impact !== pick.value;
  return (
    <span className="flex items-center gap-1.5" title={impactTitle(pick)}>
      {showValue && pick.value != null && (
        <span className="num text-[var(--fs-xs)] text-faint">val {num(pick.value)}</span>
      )}
      <Badge variant={tone}>
        {impact > 0 ? "+" : ""}
        {num(impact)}
      </Badge>
    </span>
  );
}

/** Marks a genuine season-long 0 — drafted but never played (injury / IR / ineligible).
 *  The points really are 0 (not missing); the tooltip carries the why. */
function DnpMark({ detail }: { detail?: string | null }) {
  return (
    <span className="dz-eyebrow ml-1 align-middle text-faint" title={detail ?? "Did not play all season"}>
      DNP
    </span>
  );
}

function compactPlayerName(name: string | null | undefined) {
  if (!name) return "—";
  const parts = name.trim().split(/\s+/);
  if (parts.length < 2) return name;
  if (/^(?:[A-Z]\.){1,3}$/i.test(parts[0])) return name;
  return `${parts[0][0]}. ${parts.slice(1).join(" ")}`;
}

function compactPoints(points: number | null | undefined) {
  if (points == null) return "—";
  return `${num(points).replace(/\.00$/, "")} pts`;
}

function PickCell({ pick, focused }: { pick: Pick; focused?: boolean }) {
  const ownerLabel = pick.owner_name ?? pick.team_name ?? "—";
  const teamSub =
    pick.team_name && pick.owner_name && !pick.team_name.toLowerCase().includes(pick.owner_name.toLowerCase())
      ? pick.team_name
      : null;

  return (
    <Link
      to={pick.player_id != null ? `/players/${pick.player_id}` : "#"}
      title={pick.player_name ?? undefined}
      className={`flex min-h-36 min-w-0 flex-col rounded-[var(--radius-sm)] border bg-[var(--surface-1)] p-2.5 transition-colors hover:border-[var(--accent)] ${
        focused ? "border-[var(--accent)] ring-1 ring-[var(--accent)]" : "border-[var(--border)]"
      }`}
    >
      <div className="mb-2 space-y-1">
        <span className="num block text-[var(--fs-xs)] text-faint">#{pick.overall}</span>
        <div className="min-w-0">
          {pick.available ? <ValueTag value={pick.value} /> : <DataGap reason={pick.reason ?? undefined} size="sm" />}
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold leading-snug text-text">
          {compactPlayerName(pick.player_name)}
        </div>
        <div className="mt-1 space-y-0.5 text-[var(--fs-xs)] text-muted">
          <span>{pick.position ?? "—"}</span>
          <span className="num block truncate">
            {compactPoints(pick.season_points)}
            {pick.zero_reason === "did_not_play_season" && <DnpMark detail={pick.zero_detail} />}
          </span>
        </div>
      </div>
      <div className="mt-2 min-w-0 border-l-2 border-[var(--border-strong)] pl-2 leading-tight">
        <div className="truncate text-[var(--fs-xs)] font-semibold text-text">{ownerLabel}</div>
        {teamSub && <div className="mt-0.5 truncate text-[var(--fs-xs)] text-faint">{teamSub}</div>}
      </div>
    </Link>
  );
}

function orderedRoundPicks(round: number, picks: Pick[]) {
  const ordered = [...picks].sort((a, b) => (a.pick_in_round ?? a.overall) - (b.pick_in_round ?? b.overall));
  return round % 2 === 0 ? ordered.reverse() : ordered;
}

/** A steal/bust leaderboard row, deep-linking to the drafted player. */
function PickLine({
  pick,
  rank,
  lens,
  onFocus,
}: {
  pick: Pick;
  rank: number;
  lens: Lens;
  onFocus: (overall: number) => void;
}) {
  const teamLabel = pick.team_name ?? pick.owner_name ?? "—";
  return (
    <button
      type="button"
      onClick={() => onFocus(pick.overall)}
      className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-[var(--radius-sm)] px-2 py-1.5 text-left hover:bg-[var(--surface-1)]"
    >
      <span className="grid min-w-0 grid-cols-[1rem_minmax(0,1fr)] gap-2">
        <span className="num text-[var(--fs-xs)] text-faint">{rank}</span>
        <span className="min-w-0">
          <span className="flex min-w-0 items-center gap-1">
            <span className="truncate font-medium text-text" title={pick.player_name ?? undefined}>
              {pick.player_name ?? "—"}
            </span>
            {pick.zero_reason === "did_not_play_season" && <DnpMark detail={pick.zero_detail} />}
          </span>
          <span className="block truncate text-[var(--fs-xs)] text-faint" title={teamLabel}>
            #{pick.overall} · {teamLabel}
          </span>
        </span>
      </span>
      {lens === "weighted" ? <ImpactTag pick={pick} /> : <ValueTag value={pick.value} />}
    </button>
  );
}

function LeaderboardList({
  picks,
  lens,
  visible,
  onVisible,
  onFocus,
}: {
  picks: Pick[];
  lens: Lens;
  visible: number;
  onVisible: (count: number) => void;
  onFocus: (overall: number) => void;
}) {
  const shown = picks.slice(0, visible);
  return (
    <div className="space-y-1 p-3">
      {shown.map((pick, index) => (
        <PickLine
          key={pick.overall}
          pick={pick}
          rank={index + 1}
          lens={lens}
          onFocus={onFocus}
        />
      ))}
      {picks.length > 3 && (
        <div className="flex justify-end gap-2 px-2 pt-1">
          {visible > 3 && (
            <Button variant="ghost" onClick={() => onVisible(3)}>
              Collapse
            </Button>
          )}
          {visible < picks.length && (
            <Button variant="ghost" onClick={() => onVisible(Math.min(visible + 3, picks.length))}>
              Show 3 more
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function DraftPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const [position, setPosition] = useState("");
  const [round, setRound] = useState("");
  const [team, setTeam] = useState("");
  const [lens, setLens] = useState<Lens>("weighted");
  const [chartOrder, setChartOrder] = useState<ChartOrder>("metric");
  const [stealsVisible, setStealsVisible] = useState(3);
  const [bustsVisible, setBustsVisible] = useState(3);
  const [focusedOverall, setFocusedOverall] = useState<number | null>(null);

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

  const positions = useMemo(
    () => Array.from(new Set(value.data?.picks.map((p) => p.position).filter(Boolean))).sort(),
    [value.data?.picks],
  );
  const rounds = useMemo(
    () => Array.from(new Set(value.data?.picks.map((p) => p.round).filter(Boolean))).sort((a, b) => a - b),
    [value.data?.picks],
  );
  const teams = useMemo(() => {
    const byId = new Map<number, string>();
    for (const pick of value.data?.picks ?? []) {
      byId.set(pick.team_id, pick.owner_name ? `${pick.owner_name} — ${pick.team_name ?? "Team"}` : (pick.team_name ?? "Team"));
    }
    return Array.from(byId, ([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label));
  }, [value.data?.picks]);

  useEffect(() => {
    setStealsVisible(3);
    setBustsVisible(3);
    setFocusedOverall(null);
  }, [seasonId, lens]);

  // Clear the chart filters when the season changes — a position/team/round
  // present in one season may not exist in the next, and a stale filter would
  // otherwise silently empty the chart.
  useEffect(() => {
    setPosition("");
    setRound("");
    setTeam("");
  }, [seasonId]);

  const weightedSteals = value.data?.steals ?? [];
  const weightedBusts = value.data?.busts ?? [];
  const pointsSteals = value.data?.points_steals ?? [];
  const pointsBusts = value.data?.points_busts ?? [];
  const steals = lens === "weighted" ? weightedSteals : pointsSteals;
  const busts = lens === "weighted" ? weightedBusts : pointsBusts;
  const metricOf = (p: Pick) => (lens === "weighted" ? p.impact : p.value);
  // Picks matching the filter controls, independent of whether they have a
  // value for the active lens. Kept separate from `chartRows` so the empty
  // state can tell "nothing matched the filter" apart from "matched, but this
  // lens has no number for them" (e.g. a kicker under the weighted lens).
  const matchedPicks = (value.data?.picks ?? []).filter((p) => {
    if (position && p.position !== position) return false;
    if (round && p.round !== Number(round)) return false;
    if (team && p.team_id !== Number(team)) return false;
    return true;
  });
  const chartRows = matchedPicks
    .filter((p) => metricOf(p) != null)
    .sort((a, b) => {
      if (chartOrder === "draft") return a.overall - b.overall;
      return (metricOf(b) ?? Number.NEGATIVE_INFINITY) - (metricOf(a) ?? Number.NEGATIVE_INFINITY);
    })
    .map((p) => ({
      label: `#${p.overall} ${(p.player_name ?? "").split(" ").slice(-1)[0]}`,
      metric: metricOf(p) as number,
      __note: `${p.player_name ?? "Unknown"} · ${p.position ?? "—"} · ${p.team_name ?? p.owner_name ?? "—"} · raw value ${num(p.value)}`,
    }));
  const hasPicks = (value.data?.picks?.length ?? 0) > 0;
  // Why the chart is empty under the current filter + lens, phrased honestly.
  const emptyChartMessage =
    matchedPicks.length === 0
      ? "No picks match these filters."
      : lens === "weighted"
        ? "These picks aren’t part of the position-normalized impact model — kickers, defenses, and unscored picks are excluded. Switch to the Points lens to compare them."
        : "These picks have no scored value yet.";

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
          {value.data?.available && (steals.length > 0 || busts.length > 0) && (
            <div className="space-y-2">
            <Tabs
              tabs={[
                { id: "weighted", label: "Weighted" },
                { id: "points", label: "Points" },
              ]}
              value={lens}
              onChange={setLens}
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader eyebrow="outperformed their slot" title="Steals" />
                {steals.length === 0 ? (
                    <p className="px-2 py-1.5 text-[var(--fs-sm)] text-faint">No clear steals.</p>
                ) : (
                  <LeaderboardList
                    picks={steals}
                    lens={lens}
                    visible={stealsVisible}
                    onVisible={setStealsVisible}
                    onFocus={setFocusedOverall}
                  />
                )}
              </Card>
              <Card>
                <CardHeader eyebrow="fell short of their slot" title="Busts" />
                {busts.length === 0 ? (
                    <p className="px-2 py-1.5 text-[var(--fs-sm)] text-faint">No clear busts.</p>
                ) : (
                  <LeaderboardList
                    picks={busts}
                    lens={lens}
                    visible={bustsVisible}
                    onVisible={setBustsVisible}
                    onFocus={setFocusedOverall}
                  />
                )}
              </Card>
            </div>
            {lens === "weighted" && value.data.impact_definition && (
              <p className="max-w-prose px-1 text-[var(--fs-xs)] text-faint">
                {value.data.impact_definition}
              </p>
            )}
            {lens === "points" && value.data.definition && (
              <p className="max-w-prose px-1 text-[var(--fs-xs)] text-faint">{value.data.definition}</p>
            )}
            </div>
          )}

          {hasPicks && (
            <Card>
              <CardHeader
                eyebrow={lens === "weighted" ? "position-normalized weighted impact" : "points above / below slot expectation"}
                title={lens === "weighted" ? "Weighted impact" : "Pick value"}
              />
              <div className="flex flex-wrap gap-2 px-5 pt-5">
                <select aria-label="Filter by position" className="dz-input" value={position} onChange={(e) => setPosition(e.target.value)}>
                  <option value="">All positions</option>
                  {positions.map((p) => (
                    <option key={p} value={p ?? ""}>
                      {p}
                    </option>
                  ))}
                </select>
                <select aria-label="Filter by round" className="dz-input" value={round} onChange={(e) => setRound(e.target.value)}>
                  <option value="">All rounds</option>
                  {rounds.map((r) => (
                    <option key={r} value={r}>
                      Round {r}
                    </option>
                  ))}
                </select>
                <select aria-label="Filter by team" className="dz-input" value={team} onChange={(e) => setTeam(e.target.value)}>
                  <option value="">All teams</option>
                  {teams.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <select aria-label="Sort chart" className="dz-input" value={chartOrder} onChange={(e) => setChartOrder(e.target.value as ChartOrder)}>
                  <option value="metric">{lens === "weighted" ? "Weighted rank" : "Points rank"}</option>
                  <option value="draft">Draft order</option>
                </select>
              </div>
              <div className="p-5">
                {chartRows.length > 0 ? (
                  <BarCompare
                    title={lens === "weighted" ? "Weighted impact by pick" : "Points value by pick"}
                    data={chartRows}
                    series={[{ key: "metric", label: lens === "weighted" ? "Weighted impact" : "Value (pts)" }]}
                    xKey="label"
                    xLabel="Pick"
                    height={220}
                  />
                ) : (
                  <p className="max-w-prose py-8 text-center text-[var(--fs-sm)] text-faint">
                    {emptyChartMessage}
                  </p>
                )}
                {lens === "points" && value.data?.definition && (
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
                  <div
                    aria-label={`Round ${rnd.round} snake picks`}
                    className="grid min-w-0 gap-2"
                    style={{ gridTemplateColumns: "repeat(12, minmax(0, 1fr))" }}
                  >
                    {orderedRoundPicks(rnd.round, rnd.picks).map((p) => (
                      <PickCell key={p.overall} pick={p} focused={p.overall === focusedOverall} />
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
