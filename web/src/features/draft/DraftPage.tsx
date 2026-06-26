import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Button, Card, CardHeader, DataGap, ErrorState, Skeleton, Tabs } from "@/design-system";
import { BarCompare, ScatterQuadrant } from "@/charts";
import type { QuadrantPoint } from "@/charts";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type Board = Awaited<ReturnType<typeof fetchBoard>>;
type Pick = Board["rounds"][number]["picks"][number];
type Tendencies = Awaited<ReturnType<typeof fetchTendencies>>;
type Manager = Tendencies["managers"][number];
type Lens = "weighted" | "points" | "market";
type ChartOrder = "metric" | "draft";
/** What each board cell reveals beneath the persistent identity line. Basic is the
 *  decluttered default; Performance swaps in the steal/bust impact; Market swaps in
 *  the ADP read. Independent of the leaderboard `Lens` above. */
type BoardView = "basic" | "performance" | "market";
type Superlative = { label: string; tone: "win" | "loss" | "default" };
type QuadrantStory = { tone: QuadrantPoint["tone"]; story: string };

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

async function fetchTendencies() {
  const { data, error } = await api.GET("/v1/draft/tendencies");
  if (error || !data) throw new Error("Failed to load draft tendencies");
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

/** Tooltip spelling out the market read: blended ADP, sources, spread, format. */
function adpTitle(pick: Pick): string | undefined {
  if (!pick.adp_available || pick.adp == null) return undefined;
  const parts = [`Blended ADP ${num(pick.adp)} (${(pick.adp_sources ?? []).join(", ") || "—"})`];
  if (pick.adp_delta != null) {
    const verb = pick.adp_delta > 0 ? "later than" : pick.adp_delta < 0 ? "earlier than" : "right on";
    parts.push(`drafted #${pick.overall} — ${verb} the market`);
  }
  if (pick.adp_source_spread) parts.push(`sources split by ${num(pick.adp_source_spread)}`);
  if (pick.adp_format) {
    parts.push(pick.adp_format_fallback ? `${pick.adp_format} (format fallback)` : pick.adp_format);
  }
  return parts.join(" · ");
}

function marketRead(pick: Pick): { label: string; amount: number; tone: "win" | "loss" | "default" } | null {
  if (!pick.adp_available || pick.adp_delta == null) return null;
  const amount = Math.abs(pick.adp_delta);
  if (pick.market_label === "reach") return { label: "Reach by", amount, tone: "loss" };
  if (pick.market_label === "value") return { label: "Value by", amount, tone: "win" };
  return { label: "On market", amount, tone: "default" };
}

/** Reach/value delta, phrased without relying on sign interpretation. */
function AdpTag({ pick }: { pick: Pick }) {
  const read = marketRead(pick);
  if (!read) return null;
  return (
    <Badge variant={read.tone}>
      {read.label} {num(read.amount)}
    </Badge>
  );
}

/** Compact board-cell market line, phrased as a read rather than a signed number. */
function MarketChip({ pick }: { pick: Pick }) {
  if (!pick.adp_available || pick.adp == null || pick.adp_delta == null) return null;
  const read = marketRead(pick);
  if (!read) return null;
  const tone = read.tone === "win" ? "text-win" : read.tone === "loss" ? "text-loss" : "text-muted";
  return (
    <span
      className="mt-1 inline-flex max-w-full items-center gap-1 rounded-sm border border-[var(--hairline)] px-1.5 py-0.5 text-[10px]"
      title={adpTitle(pick)}
    >
      <span className="num text-faint">ADP {num(pick.adp)}</span>
      <span className={`truncate ${tone}`}>
        {read.label} <span className="num">{num(read.amount)}</span>
      </span>
      {pick.adp_format_fallback && (
        <span className="text-faint" title="ADP format fallback — not the league's target format">
          *
        </span>
      )}
    </span>
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
function ImpactTag({ pick, compact = false }: { pick: Pick; compact?: boolean }) {
  const impact = pick.impact ?? pick.value;
  if (impact == null) return null;
  const tone = impact > 0 ? "win" : impact < 0 ? "loss" : "default";
  const showValue = !compact && pick.impact != null && pick.value != null && pick.impact !== pick.value;
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

function quadrantStory(adpDelta: number, impact: number): QuadrantStory {
  if (adpDelta >= 0 && impact >= 0) return { tone: "value_hit", story: "Value that hit" };
  if (adpDelta < 0 && impact < 0) return { tone: "reach_bust", story: "Reach that busted" };
  if (adpDelta < 0 && impact >= 0) return { tone: "reach_hit", story: "Reach that hit" };
  return { tone: "value_miss", story: "Value that missed" };
}

/** A one-word "headline of the draft" chip — the top steal/bust/reach/value. Kept
 *  rare (only the leader of each list) so it stays a callout, not clutter. */
function SuperlativeChip({ label, tone }: Superlative) {
  const cls = tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : "text-accent";
  return (
    <span
      className={`dz-eyebrow mt-1 inline-flex items-center rounded-sm border border-[var(--hairline)] px-1 py-0.5 text-[9px] ${cls}`}
    >
      {label}
    </span>
  );
}

/** One board cell. The identity line — pick #, player, position · NFL team, owner —
 *  is persistent across every view; only the metric beneath it changes with `view`,
 *  so the whole board can be scanned through one lens at a time without crowding. */
function PickCell({
  pick,
  focused,
  view,
  superlative,
}: {
  pick: Pick;
  focused?: boolean;
  view: BoardView;
  superlative?: Superlative;
}) {
  const ownerLabel = pick.owner_name ?? pick.team_name ?? "—";
  const teamSub =
    pick.team_name && pick.owner_name && !pick.team_name.toLowerCase().includes(pick.owner_name.toLowerCase())
      ? pick.team_name
      : null;
  const posTeam = pick.nfl_team ? `${pick.position ?? "—"} · ${pick.nfl_team}` : (pick.position ?? "—");

  return (
    <Link
      to={pick.player_id != null ? `/players/${pick.player_id}` : "#"}
      title={pick.player_name ?? undefined}
      className={`flex min-h-36 min-w-0 flex-col rounded-[var(--radius-sm)] border bg-[var(--surface-1)] p-2.5 transition-colors hover:border-[var(--accent)] ${
        focused ? "border-[var(--accent)] ring-1 ring-[var(--accent)]" : "border-[var(--border)]"
      }`}
    >
      {view === "basic" ? (
        <>
          <div className="mb-2 flex min-h-[1.25rem] items-start justify-between gap-1">
            <span className="num text-[var(--fs-xs)] text-faint">#{pick.overall}</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-semibold leading-snug text-text">
              {compactPlayerName(pick.player_name)}
            </div>
            <div className="mt-1 text-[var(--fs-xs)] text-muted">
              <span className="block truncate">{posTeam}</span>
            </div>
          </div>
          <div className="mt-2 min-w-0 border-l-2 border-[var(--border-strong)] pl-2 leading-tight">
            <div className="truncate text-[var(--fs-xs)] font-semibold text-text">{ownerLabel}</div>
            {teamSub && <div className="mt-0.5 truncate text-[var(--fs-xs)] text-faint">{teamSub}</div>}
          </div>
        </>
      ) : (
        // Performance / Market: stripped to player + the view's metric + owner, so
        // the relevant number reads cleanly. Pick # and position · team are retained
        // but demoted to a faint top row that truncates first when space is tight.
        <>
          <div className="mb-1.5 flex items-center justify-between gap-1.5 text-[var(--fs-xs)] text-faint">
            <span className="num shrink-0">#{pick.overall}</span>
            <span className="min-w-0 truncate">{posTeam}</span>
          </div>
          <div className="truncate text-[13px] font-semibold leading-snug text-text">
            {compactPlayerName(pick.player_name)}
          </div>
          <div className="mt-1.5 flex min-w-0 flex-1 flex-col items-start gap-1">
            {view === "performance" ? (
              pick.available ? (
                <>
                  <ImpactTag pick={pick} compact />
                  {pick.season_points != null && (
                    <span
                      className="text-[var(--fs-xs)] text-faint"
                      title="Regular-season fantasy points — the weeks the board's value and impact are measured over (excludes the fantasy playoffs)."
                    >
                      <span className="num">{num(pick.season_points).replace(/\.00$/, "")}</span> reg-szn pts
                      {pick.zero_reason === "did_not_play_season" && <DnpMark detail={pick.zero_detail} />}
                    </span>
                  )}
                </>
              ) : (
                <DataGap reason={pick.reason ?? undefined} size="sm" />
              )
            ) : (
              <MarketChip pick={pick} />
            )}
            {view === "market" && !(pick.adp_available && pick.adp != null && pick.adp_delta != null) && (
              <span className="text-[var(--fs-xs)] text-faint">no ADP</span>
            )}
            {superlative && <SuperlativeChip {...superlative} />}
          </div>
          <div className="mt-2 min-w-0 truncate border-l-2 border-[var(--border-strong)] pl-2 text-[var(--fs-xs)] font-semibold leading-tight text-text">
            {ownerLabel}
          </div>
        </>
      )}
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
      {lens === "weighted" ? (
        <ImpactTag pick={pick} />
      ) : lens === "market" ? (
        <AdpTag pick={pick} />
      ) : (
        <ValueTag value={pick.value} />
      )}
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

/** One manager's market tendencies row. The language avoids signed deltas; a thin
 *  sample is dimmed but never hidden — the honest pick count stays visible. */
function TendencyRow({ m }: { m: Manager }) {
  const tendency =
    m.mean_delta > 0 ? { label: "waits", amount: m.mean_delta, tone: "text-win" }
    : m.mean_delta < 0 ? { label: "reaches", amount: Math.abs(m.mean_delta), tone: "text-loss" }
    : { label: "on market", amount: 0, tone: "text-muted" };
  const positions = m.by_position
    .map((p) => {
      const label = p.mean_delta > 0 ? "waits" : p.mean_delta < 0 ? "reaches" : "on market";
      return `${p.position} ${label} ${num(Math.abs(p.mean_delta))} (${p.n})`;
    })
    .join(" · ");
  return (
    <tr className={`border-t border-[var(--border)] ${m.sufficient ? "" : "opacity-60"}`}>
      <td className="py-1.5 pr-3">
        <span className="font-medium text-text">{m.owner_name ?? m.team_name ?? "—"}</span>
        {!m.qualified && <span className="dz-eyebrow ml-1 text-faint">(short stint)</span>}
        {positions && <span className="block truncate text-[var(--fs-xs)] text-faint" title={positions}>{positions}</span>}
      </td>
      <td className="py-1.5 pr-3 text-right num">{m.n_picks_with_adp}</td>
      <td className="py-1.5 pr-3 text-right num">{Math.round(m.reach_rate * 100)}%</td>
      <td className={`py-1.5 pr-3 text-right ${tendency.tone}`}>
        <span className="font-medium">{tendency.label}</span>{" "}
        <span className="num">{num(tendency.amount)}</span>
      </td>
      <td className="py-1.5 pr-3 text-right num">{num(m.discipline)}</td>
    </tr>
  );
}

export function DraftPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const [position, setPosition] = useState("");
  const [round, setRound] = useState("");
  const [team, setTeam] = useState("");
  const [lens, setLens] = useState<Lens>("weighted");
  const [boardView, setBoardView] = useState<BoardView>("basic");
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

  // Outcome axis (weighted / points) shares the steals|busts shape; the market
  // axis swaps in reaches|values (drafted earlier vs later than consensus).
  const leftPicks =
    lens === "weighted" ? (value.data?.steals ?? [])
    : lens === "points" ? (value.data?.points_steals ?? [])
    : (value.data?.reaches ?? []);
  const rightPicks =
    lens === "weighted" ? (value.data?.busts ?? [])
    : lens === "points" ? (value.data?.points_busts ?? [])
    : (value.data?.values ?? []);
  const leftMeta =
    lens === "market"
      ? { title: "Reaches", eyebrow: "took earlier than consensus" }
      : { title: "Steals", eyebrow: "outperformed their slot" };
  const rightMeta =
    lens === "market"
      ? { title: "Values", eyebrow: "waited longer than consensus" }
      : { title: "Busts", eyebrow: "fell short of their slot" };
  const metricOf = (p: Pick) =>
    lens === "weighted" ? p.impact : lens === "market" ? p.adp_delta : p.value;
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
        : lens === "market"
          ? "These picks have no consensus ADP — they fell outside the public market (deep picks, most kickers and defenses, rookies)."
          : "These picks have no scored value yet.";

  // Reach × outcome quadrant: x = market axis (reach ↔ value), y = outcome axis.
  // Only picks with both a delta and an impact appear; the four quadrants tell the
  // "reached and it busted" vs "waited and it hit" stories.
  const quadrantPoints: QuadrantPoint[] = useMemo(() => {
    if (lens !== "market") return [];
    return (value.data?.picks ?? [])
      .filter((p) => p.adp_delta != null && p.impact != null)
      .map((p) => {
        const x = p.adp_delta as number;
        const y = p.impact as number;
        return {
          x,
          y,
          ...quadrantStory(x, y),
          label: `#${p.overall} ${(p.player_name ?? "").split(" ").slice(-1)[0]}`,
          note: `${p.position ?? "—"} · ${p.team_name ?? p.owner_name ?? "—"}`,
        };
      });
  }, [lens, value.data?.picks]);

  // Board "headline" callouts: only the single leader of each list earns a chip,
  // so a superlative stays a rare flourish rather than another column of noise.
  // The lists are already ranked best-first by the BFF.
  const boardSuperlatives = useMemo(() => {
    const map = new Map<number, Superlative>();
    const v = value.data;
    if (!v) return map;
    if (boardView === "performance") {
      if (v.steals[0]) map.set(v.steals[0].overall, { label: "Top steal", tone: "win" });
      if (v.busts[0]) map.set(v.busts[0].overall, { label: "Top bust", tone: "loss" });
    } else if (boardView === "market") {
      if (v.reaches?.[0]) map.set(v.reaches[0].overall, { label: "Biggest reach", tone: "loss" });
      if (v.values?.[0]) map.set(v.values[0].overall, { label: "Best value", tone: "win" });
    }
    return map;
  }, [boardView, value.data]);

  const tendencies = useQuery({
    queryKey: qk.draftTendencies(),
    queryFn: fetchTendencies,
    enabled: board.data?.available === true && lens === "market",
  });

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
          {value.data?.available && (leftPicks.length > 0 || rightPicks.length > 0) && (
            <div className="space-y-2">
            <Tabs
              tabs={[
                { id: "weighted", label: "Weighted" },
                { id: "points", label: "Points" },
                { id: "market", label: "Reach / value" },
              ]}
              value={lens}
              onChange={setLens}
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader eyebrow={leftMeta.eyebrow} title={leftMeta.title} />
                {leftPicks.length === 0 ? (
                    <p className="px-2 py-1.5 text-[var(--fs-sm)] text-faint">No clear {leftMeta.title.toLowerCase()}.</p>
                ) : (
                  <LeaderboardList
                    picks={leftPicks}
                    lens={lens}
                    visible={stealsVisible}
                    onVisible={setStealsVisible}
                    onFocus={setFocusedOverall}
                  />
                )}
              </Card>
              <Card>
                <CardHeader eyebrow={rightMeta.eyebrow} title={rightMeta.title} />
                {rightPicks.length === 0 ? (
                    <p className="px-2 py-1.5 text-[var(--fs-sm)] text-faint">No clear {rightMeta.title.toLowerCase()}.</p>
                ) : (
                  <LeaderboardList
                    picks={rightPicks}
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
            {lens === "market" && value.data.adp_definition && (
              <p className="max-w-prose px-1 text-[var(--fs-xs)] text-faint">{value.data.adp_definition}</p>
            )}
            </div>
          )}

          {hasPicks && (
            <Card>
              <CardHeader
                eyebrow={
                  lens === "weighted"
                    ? "position-normalized weighted impact"
                    : lens === "market"
                      ? "drafted earlier (reach) / later (value) than consensus"
                      : "points above / below slot expectation"
                }
                title={lens === "weighted" ? "Weighted impact" : lens === "market" ? "Reach / value" : "Pick value"}
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
                  <option value="metric">
                    {lens === "weighted" ? "Weighted rank" : lens === "market" ? "Reach / value rank" : "Points rank"}
                  </option>
                  <option value="draft">Draft order</option>
                </select>
              </div>
              <div className="p-5">
                {chartRows.length > 0 ? (
                  <BarCompare
                    title={
                      lens === "weighted"
                        ? "Weighted impact by pick"
                        : lens === "market"
                          ? "Market gap by pick"
                          : "Points value by pick"
                    }
                    data={chartRows}
                    series={[
                      {
                        key: "metric",
                        label:
                          lens === "weighted"
                            ? "Weighted impact"
                            : lens === "market"
                              ? "Market gap (picks)"
                              : "Value (pts)",
                      },
                    ]}
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

          {lens === "market" && quadrantPoints.length > 1 && (
            <Card>
              <CardHeader eyebrow="market axis × outcome axis" title="Reach / value vs outcome" />
              <div className="p-5">
                <div className="mb-3 flex flex-wrap gap-3 text-[var(--fs-xs)] text-faint">
                  <span><span className="text-win">Green</span> = value that hit</span>
                  <span><span className="text-loss">Red</span> = reach that busted</span>
                  <span><span className="text-accent">Gold</span> = reach that hit or value that missed</span>
                </div>
                <ScatterQuadrant
                  points={quadrantPoints}
                  title="Reach/value vs outcome by pick"
                  xLabel="Reached earlier ← → Waited longer"
                  yLabel="Bust ← → Steal"
                  height={300}
                />
                <p className="mt-3 max-w-prose text-[var(--fs-xs)] text-faint">
                  Right side means the league waited longer than consensus; left side means it paid up.
                  Up-right waited and it hit; down-left reached and it busted; up-left reached but it
                  worked; down-right waited and still missed. Only picks with both a consensus
                  ADP and a weighted impact appear.
                </p>
              </div>
            </Card>
          )}

          <Card>
            <CardHeader
              eyebrow={`${board.data.num_teams ?? "—"} teams`}
              title="Draft board"
              action={
                <Tabs
                  tabs={[
                    { id: "basic", label: "Basic" },
                    { id: "performance", label: "Performance" },
                    { id: "market", label: "Market" },
                  ]}
                  value={boardView}
                  onChange={setBoardView}
                />
              }
            />
            <div className="space-y-5 p-5">
              <p className="max-w-prose text-[var(--fs-xs)] text-faint">
                {boardView === "basic"
                  ? "Who went where: player, position · NFL team, owner, and season points."
                  : boardView === "performance"
                    ? "Each pick's steal/bust impact against its slot — hover a badge for the weighting."
                    : "Each pick read against consensus ADP — drafted earlier (reach) or later (value)."}
              </p>
              {board.data.rounds.map((rnd) => (
                <div key={rnd.round}>
                  <div className="dz-eyebrow mb-2">Round {rnd.round}</div>
                  <div
                    aria-label={`Round ${rnd.round} snake picks`}
                    className="grid min-w-0 gap-2"
                    style={{ gridTemplateColumns: "repeat(12, minmax(0, 1fr))" }}
                  >
                    {orderedRoundPicks(rnd.round, rnd.picks).map((p) => (
                      <PickCell
                        key={p.overall}
                        pick={p}
                        focused={p.overall === focusedOverall}
                        view={boardView}
                        superlative={boardSuperlatives.get(p.overall)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}

      {board.data?.available && lens === "market" && tendencies.data?.available && tendencies.data.managers.length > 0 && (
        <Card>
          <CardHeader
            eyebrow="experimental · across every captured draft"
            title="Manager market tendencies"
            action={<Badge variant="gap">work in progress</Badge>}
          />
          <div className="space-y-3 p-5">
            <p className="max-w-prose text-[var(--fs-sm)] text-muted">
              This is a directional read on draft style, not a grade. It asks whether a manager
              usually pays above consensus, waits for value, or stays close to the public board.
              It will get stronger with more context, so sample size stays visible.
            </p>
            <div className="grid grid-cols-1 gap-3 text-[var(--fs-xs)] text-faint md:grid-cols-3">
              <div className="rounded-[var(--radius-sm)] border border-[var(--hairline)] p-3">
                <div className="dz-eyebrow mb-1 text-loss">Reach rate</div>
                Share of ADP-covered picks taken before the public market expected.
              </div>
              <div className="rounded-[var(--radius-sm)] border border-[var(--hairline)] p-3">
                <div className="dz-eyebrow mb-1 text-win">Typical lean</div>
                "Waits" means later than consensus; "reaches" means earlier than consensus.
              </div>
              <div className="rounded-[var(--radius-sm)] border border-[var(--hairline)] p-3">
                <div className="dz-eyebrow mb-1">Discipline</div>
                Average distance from consensus. Lower means closer to the board.
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[var(--fs-sm)]">
                <thead className="dz-eyebrow text-faint">
                  <tr>
                    <th className="pb-2 pr-3">Manager</th>
                    <th className="pb-2 pr-3 text-right">Picks</th>
                    <th className="pb-2 pr-3 text-right">Reach rate</th>
                    <th className="pb-2 pr-3 text-right">Typical lean</th>
                    <th className="pb-2 pr-3 text-right">Discipline</th>
                  </tr>
                </thead>
                <tbody>
                  {tendencies.data.managers.map((m) => (
                    <TendencyRow key={m.owner_id} m={m} />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="max-w-prose text-[var(--fs-xs)] text-faint">{tendencies.data.definition}</p>
          </div>
        </Card>
      )}
    </div>
  );
}
