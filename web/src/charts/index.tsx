import type { ReactNode } from "react";
import {
  type TooltipProps,
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { type ChartTheme, chartTheme, heatColor, seriesColor, tooltipProps } from "./chartTheme";

// Thin, theme-bound wrappers over Recharts (and a CSS-grid Heatmap). Every chart
// carries an accessible title and a <details> data-table fallback so meaning
// survives without color or sight. Pages pass already-computed data — no logic here.

export type ChartRow = Record<string, number | string | null>;
export type SeriesDef = {
  key: string;
  label: string;
  color?: string;
  // Optional season-outcome marker drawn on the series' final node (the leg's
  // champion/Sacko grammar) — used by the standings rank-race.
  marker?: "champion" | "sacko";
};

function rankTooltip({
  active,
  label,
  payload,
}: TooltipProps<number | string, string>): React.ReactElement | null {
  if (!active || !payload?.length) return null;
  const t = chartTheme();
  const ranked = [...payload]
    .filter((p) => p.value != null)
    .sort((a, b) => Number(a.value) - Number(b.value));
  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.borderStrong}`,
        borderRadius: 10,
        fontFamily: t.fontMono,
        fontSize: 12,
        padding: "8px 10px",
      }}
    >
      <div style={{ color: t.text, marginBottom: 6 }}>Week {String(label)}</div>
      <div className="space-y-1">
        {ranked.map((p) => (
          <div key={p.dataKey} style={{ color: p.color ?? t.text }}>
            #{p.value} {p.name}
          </div>
        ))}
      </div>
    </div>
  );
}

function DataTable({
  data,
  series,
  xKey,
  xLabel,
}: {
  data: ChartRow[];
  series: SeriesDef[];
  xKey: string;
  xLabel: string;
}) {
  const hasNotes = data.some((row) => typeof row.__note === "string" && row.__note.length > 0);
  return (
    <table className="dz-table mt-1">
      <thead>
        <tr>
          <th>{xLabel}</th>
          {series.map((s) => (
            <th key={s.key} className="dz-num">
              {s.label}
            </th>
          ))}
          {hasNotes && <th>Note</th>}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => (
          <tr key={i}>
            <td>{String(row[xKey] ?? "—")}</td>
            {series.map((s) => (
              <td key={s.key} className="dz-num num">
                {row[s.key] ?? "—"}
              </td>
            ))}
            {hasNotes && <td>{typeof row.__note === "string" ? row.__note : ""}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ChartFrame({
  title,
  height = 240,
  table,
  children,
}: {
  title: string;
  height?: number;
  table?: ReactNode;
  children: React.ReactElement;
}) {
  return (
    <figure className="m-0" aria-label={title}>
      <figcaption className="sr-only">{title}</figcaption>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
      {table && (
        <details className="mt-2 text-[var(--fs-xs)] text-faint">
          <summary className="cursor-pointer">Data table</summary>
          {table}
        </details>
      )}
    </figure>
  );
}

type CartesianProps = {
  data: ChartRow[];
  series: SeriesDef[];
  xKey: string;
  xLabel?: string;
  title: string;
  height?: number;
  minPointSize?: number;
};

const axisTick = () => {
  const t = chartTheme();
  return { fill: t.text, fontFamily: t.fontMono, fontSize: 11 } as const;
};

/** scoring trend, standings/power over time, player weekly scoring, trajectory. */
export function LineTrend({ data, series, xKey, xLabel = xKey, title, height }: CartesianProps) {
  const t = chartTheme();
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={data} series={series} xKey={xKey} xLabel={xLabel} />}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis stroke={t.axis} tick={axisTick()} tickLine={false} width={40} />
        <Tooltip content={rankTooltip} />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color ?? seriesColor(i)}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ChartFrame>
  );
}

/** matchup team comparison, season totals, projection vs actual. */
function barTooltip({
  active,
  label,
  payload,
}: TooltipProps<number | string, string>): React.ReactElement | null {
  if (!active || !payload?.length) return null;
  const t = chartTheme();
  const note = payload.find((p) => typeof p.payload?.__note === "string")?.payload
    ?.__note as string | undefined;
  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.borderStrong}`,
        borderRadius: 10,
        fontFamily: t.fontMono,
        fontSize: 12,
        padding: "8px 10px",
      }}
    >
      <div style={{ color: t.text, marginBottom: 6 }}>{String(label)}</div>
      <div className="space-y-1">
        {payload
          .filter((p) => p.value != null)
          .map((p) => (
            <div key={p.dataKey} style={{ color: p.color ?? t.text }}>
              {p.name}: {p.value}
            </div>
          ))}
      </div>
      {note && <div style={{ color: t.text, marginTop: 6 }}>{note}</div>}
    </div>
  );
}

export function BarCompare({ data, series, xKey, xLabel = xKey, title, height, minPointSize }: CartesianProps) {
  const t = chartTheme();
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={data} series={series} xKey={xKey} xLabel={xLabel} />}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis stroke={t.axis} tick={axisTick()} tickLine={false} width={40} />
        <Tooltip content={barTooltip} cursor={{ fill: t.grid, opacity: 0.4 }} />
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color ?? seriesColor(i)} radius={[3, 3, 0, 0]} minPointSize={minPointSize} isAnimationActive={false} />
        ))}
      </BarChart>
    </ChartFrame>
  );
}

/** Zero-centered horizontal bars for a signed metric — e.g. luck (actual − expected
 *  wins): positive = gold (lucky/blessed), negative = steel-blue (robbed/unlucky), a
 *  reference line marks zero. Reusable for any +/- per-entity comparison. */
export function DivergingBars({
  data,
  title,
  xLabel = "Value",
  height,
}: {
  data: { label: string; value: number; note?: string; tone?: "pos" | "neg" }[];
  title: string;
  xLabel?: string;
  height?: number;
}) {
  const t = chartTheme();
  const rows: ChartRow[] = data.map((d) => ({ label: d.label, value: d.value, __note: d.note ?? "" }));
  const series: SeriesDef[] = [{ key: "value", label: xLabel }];
  const h = height ?? Math.max(180, data.length * 28 + 48);
  const longest = Math.max(8, ...data.map((d) => d.label.length));
  return (
    <ChartFrame title={title} height={h} table={<DataTable data={rows} series={series} xKey="label" xLabel="Entry" />}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 28, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={t.grid} horizontal={false} />
        <XAxis type="number" stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis
          type="category"
          dataKey="label"
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          width={Math.min(160, longest * 7 + 12)}
        />
        <Tooltip {...tooltipProps()} cursor={{ fill: t.grid, opacity: 0.4 }} />
        <ReferenceLine x={0} stroke={t.borderStrong} />
        <Bar dataKey="value" name={xLabel} isAnimationActive={false} radius={[0, 3, 3, 0]}>
          {data.map((d, i) => {
            const positive = d.tone ? d.tone === "pos" : d.value >= 0;
            return <Cell key={i} fill={positive ? t.gold : seriesColor(1)} />;
          })}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}

/** per-player point breakdown (passing/rushing/receiving/bonus) — stacked bars. */
export function StackedBreakdown({ data, series, xKey, xLabel = xKey, title, height }: CartesianProps) {
  const t = chartTheme();
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={data} series={series} xKey={xKey} xLabel={xLabel} />}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis stroke={t.axis} tick={axisTick()} tickLine={false} width={40} />
        <Tooltip {...tooltipProps()} cursor={{ fill: t.grid, opacity: 0.4 }} />
        <Legend wrapperStyle={{ fontFamily: t.fontMono, fontSize: 11, color: t.text }} />
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} stackId="x" fill={s.color ?? seriesColor(i)} isAnimationActive={false} />
        ))}
      </BarChart>
    </ChartFrame>
  );
}

// Rank-race dot: a small node mid-line, but the series' final node becomes the
// season-outcome marker — gold for the champion, red for the Sacko.
function makeRankDot(marker: SeriesDef["marker"], lastIndex: number, color: string, t: ChartTheme) {
  return function RankDot({ cx, cy, index }: { cx?: number; cy?: number; index?: number }) {
    if (cx == null || cy == null) return <g key={`r-${index}`} />;
    const isLast = index === lastIndex;
    if (isLast && marker) {
      const champ = marker === "champion";
      return (
        <g key={`r-${index}`}>
          <circle cx={cx} cy={cy} r={6} fill={champ ? t.gold : t.loss} stroke={t.surface} strokeWidth={1.5} />
          <title>{champ ? "Champion" : "Sacko"}</title>
        </g>
      );
    }
    return <circle key={`r-${index}`} cx={cx} cy={cy} r={2} fill={color} />;
  };
}

/** Stacked-area "stream" — e.g. cumulative league points by manager across seasons.
 *  Band thickness reads as dominance over time; a dynasty is a swelling band. */
export function StreamArea({ data, series, xKey, xLabel = xKey, title, height = 300 }: CartesianProps) {
  const t = chartTheme();
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={data} series={series} xKey={xKey} xLabel={xLabel} />}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis stroke={t.axis} tick={axisTick()} tickLine={false} width={48} />
        <Tooltip {...tooltipProps()} />
        <Legend wrapperStyle={{ fontFamily: t.fontMono, fontSize: 11, color: t.text }} />
        {series.map((s, i) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stackId="1"
            stroke={s.color ?? seriesColor(i)}
            fill={s.color ?? seriesColor(i)}
            fillOpacity={0.55}
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    </ChartFrame>
  );
}

/** standings-over-time as a bump/rank chart — one line per team, rank 1 on top.
 *  A series' `marker` flags its final node (gold champion / red Sacko). `animate`
 *  plays a one-shot intro (default off so existing callers + tests stay stable). */
export function RankFlow({
  data,
  series,
  xKey,
  xLabel = xKey,
  title,
  height,
  teamCount,
  animate = false,
}: CartesianProps & { teamCount: number; animate?: boolean }) {
  const t = chartTheme();
  const lastIndex = data.length - 1;
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={data} series={series} xKey={xKey} xLabel={xLabel} />}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis
          reversed
          domain={[1, teamCount]}
          allowDecimals={false}
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          width={28}
        />
        <Tooltip {...tooltipProps()} />
        <Legend wrapperStyle={{ fontFamily: t.fontMono, fontSize: 11, color: t.text }} />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color ?? seriesColor(i)}
            strokeWidth={2}
            dot={makeRankDot(s.marker, lastIndex, s.color ?? seriesColor(i), t)}
            isAnimationActive={animate}
          />
        ))}
      </LineChart>
    </ChartFrame>
  );
}

// ── Career legacy-spine ──────────────────────────────────────────────────────
// One manager's final finish across seasons (rank 1 on top), with gold = champion
// and red = Sacko nodes. Null finish = an honest gap (the line breaks; never a 0).
// Establishes the leg-wide champion/Sacko marker grammar that later charts reuse.

export type LegacySpineSeason = {
  season_year: number | null;
  final_rank: number | null; // null = a gap (in-progress / rank-less), never 0
  is_champion: boolean;
  is_sacko: boolean;
};

type SpineRow = ChartRow & { year: string; finish: number | null; kind: string };

type LegacyDotProps = { cx?: number; cy?: number; index?: number; payload?: SpineRow };

/** Recharts custom-dot renderer bound to the theme: a colored node per season,
 *  larger + outlined for champion (gold) / Sacko (red), nothing for a gap. */
function makeLegacyDot(t: ChartTheme, normal: string) {
  return function LegacyDot({ cx, cy, index, payload }: LegacyDotProps) {
    if (cx == null || cy == null || payload?.finish == null) {
      return <g key={`gap-${index}`} />;
    }
    const champ = payload.kind === "champion";
    const sacko = payload.kind === "sacko";
    const fill = champ ? t.gold : sacko ? t.loss : normal;
    const label = champ
      ? `Champion · ${payload.year}`
      : sacko
        ? `Sacko · ${payload.year}`
        : `${payload.year}`;
    return (
      <g key={`dot-${index}`}>
        <circle
          cx={cx}
          cy={cy}
          r={champ || sacko ? 5 : 3}
          fill={fill}
          stroke={champ || sacko ? t.surface : "none"}
          strokeWidth={champ || sacko ? 1.5 : 0}
        />
        <title>{label}</title>
      </g>
    );
  };
}

export function LegacySpine({
  seasons,
  fieldSize,
  title,
  height = 240,
}: {
  seasons: LegacySpineSeason[];
  fieldSize?: number;
  title: string;
  height?: number;
}) {
  const t = chartTheme();
  const ranks = seasons.map((s) => s.final_rank ?? 0).filter((r) => r > 0);
  // Deepest finish on record bounds the axis; floor of 8 so a small field doesn't
  // crush the scale, and any explicit fieldSize wins.
  const maxRank = Math.max(fieldSize ?? 0, 8, ...ranks);
  const rows: SpineRow[] = seasons.map((s) => ({
    year: String(s.season_year ?? "—"),
    finish: s.final_rank,
    kind: s.is_champion ? "champion" : s.is_sacko ? "sacko" : "normal",
    // Surfaced in the data-table fallback so the markers survive without color/sight.
    __note: s.is_champion ? "Champion" : s.is_sacko ? "Sacko" : "",
  }));
  const series: SeriesDef[] = [{ key: "finish", label: "Finish" }];
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={rows} series={series} xKey="year" xLabel="Season" />}>
      <LineChart data={rows} margin={{ top: 12, right: 14, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="year" stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis
          reversed
          domain={[1, maxRank]}
          allowDecimals={false}
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          width={28}
        />
        <Tooltip {...tooltipProps()} />
        <Line
          type="monotone"
          dataKey="finish"
          name="Finish"
          stroke={seriesColor(0)}
          strokeWidth={2}
          connectNulls={false}
          dot={makeLegacyDot(t, seriesColor(0))}
          activeDot={{ r: 5 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartFrame>
  );
}

/** rivalry win-pct matrix. Plain CSS grid (per the handoff), not Recharts.
 *  values[r][c] = row owner's win-pct vs col owner (0–100); null = never met /
 *  pre-coverage → a quiet "no history" cell (faint hatch + dash), never 0.
 *  rowInactive/colInactive dim departed managers when they're toggled on. */
export function Heatmap({
  rows,
  cols,
  values,
  title,
  selected,
  onSelect,
  rowInactive,
  colInactive,
}: {
  rows: string[];
  cols: string[];
  values: (number | null)[][];
  title: string;
  selected?: { r: number; c: number } | null;
  onSelect?: (r: number, c: number) => void;
  rowInactive?: boolean[];
  colInactive?: boolean[];
}) {
  const template = `minmax(64px, 1fr) repeat(${cols.length}, minmax(28px, 1fr))`;
  return (
    <figure className="m-0 overflow-x-auto" aria-label={title}>
      <figcaption className="sr-only">{title}</figcaption>
      <div role="grid" className="grid gap-px" style={{ gridTemplateColumns: template, minWidth: cols.length * 32 + 64 }}>
        <div role="columnheader" aria-hidden />
        {cols.map((c, ci) => (
          <div
            key={c}
            role="columnheader"
            title={colInactive?.[ci] ? `${c} (inactive manager)` : undefined}
            className={`truncate p-1 text-center font-mono text-[10px] uppercase text-faint${colInactive?.[ci] ? " dz-heat-dim" : ""}`}
          >
            {c}
          </div>
        ))}
        {rows.map((rowName, r) => (
          <div key={rowName} role="row" className="contents">
            <div
              role="rowheader"
              title={rowInactive?.[r] ? `${rowName} (inactive manager)` : undefined}
              className={`truncate p-1 text-right font-mono text-[11px] text-muted${rowInactive?.[r] ? " dz-heat-dim" : ""}`}
            >
              {rowName}
            </div>
            {cols.map((_, c) => {
              const v = values[r]?.[c] ?? null;
              const diagonal = r === c;
              const isSel = selected?.r === r && selected?.c === c;
              const interactive = !diagonal && v !== null && !!onSelect;
              if (v === null && !diagonal) {
                return (
                  <div
                    key={c}
                    role="gridcell"
                    title="never met / not in coverage"
                    aria-label={`${rowName} vs ${cols[c]}: no recorded history`}
                    className="dz-heat-empty grid place-items-center"
                    style={{ minHeight: 28 }}
                  >
                    <span aria-hidden>·</span>
                  </div>
                );
              }
              return (
                <div
                  key={c}
                  role="gridcell"
                  tabIndex={interactive ? 0 : -1}
                  aria-label={diagonal ? `${rowName} (self)` : `${rowName} vs ${cols[c]}: ${v}%`}
                  aria-selected={isSel || undefined}
                  onClick={interactive ? () => onSelect!(r, c) : undefined}
                  onKeyDown={
                    interactive
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onSelect!(r, c);
                          }
                        }
                      : undefined
                  }
                  className="grid place-items-center font-mono text-[10px] text-[#0b0e13] transition-transform"
                  style={{
                    minHeight: 28,
                    background: diagonal ? "var(--surface-2)" : heatColor(v as number),
                    cursor: interactive ? "pointer" : "default",
                    boxShadow: isSel ? "var(--glow-accent)" : undefined,
                  }}
                >
                  {!diagonal && v}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </figure>
  );
}

export type QuadrantPoint = {
  x: number;
  y: number;
  label: string;
  tone?: "value_hit" | "reach_bust" | "reach_hit" | "value_miss" | "mixed";
  /** extra tooltip context, e.g. "RB · #14 · Goose". */
  note?: string;
  /** quadrant story, e.g. "Reach that hit". */
  story?: string;
};

function quadrantTooltip({
  active,
  payload,
}: TooltipProps<number | string, string>): React.ReactElement | null {
  if (!active || !payload?.length) return null;
  const t = chartTheme();
  const p = payload[0]?.payload as QuadrantPoint | undefined;
  if (!p) return null;
  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.borderStrong}`,
        borderRadius: 10,
        fontFamily: t.fontMono,
        fontSize: 12,
        padding: "8px 10px",
      }}
    >
      <div style={{ color: t.text, marginBottom: 4 }}>{p.label}</div>
      {p.story && <div style={{ color: t.text, marginBottom: 4 }}>{p.story}</div>}
      {p.note && <div style={{ color: t.axis, marginBottom: 4 }}>{p.note}</div>}
      <div style={{ color: t.text }}>
        {p.x >= 0 ? "value" : "reach"} {p.x > 0 ? "+" : ""}
        {p.x} · {p.y >= 0 ? "steal" : "bust"} {p.y > 0 ? "+" : ""}
        {p.y}
      </div>
    </div>
  );
}

/** Reach × outcome quadrant: x = market axis (reach ↔ value), y = outcome axis
 *  (bust ↔ steal). Zero reference lines split the four stories (reached-and-busted,
 *  late gem, …). Pages pass already-computed points. */
export function ScatterQuadrant({
  points,
  title,
  xLabel,
  yLabel,
  height = 280,
}: {
  points: QuadrantPoint[];
  title: string;
  xLabel: string;
  yLabel: string;
  height?: number;
}) {
  const t = chartTheme();
  const colors = {
    value_hit: "var(--win)",
    reach_bust: "var(--loss)",
    reach_hit: seriesColor(3),
    value_miss: seriesColor(3),
    mixed: seriesColor(3),
  };
  const byTone = {
    value_hit: points.filter((p) => p.tone === "value_hit"),
    reach_bust: points.filter((p) => p.tone === "reach_bust"),
    reach_hit: points.filter((p) => p.tone === "reach_hit"),
    value_miss: points.filter((p) => p.tone === "value_miss"),
    mixed: points.filter((p) => !p.tone || p.tone === "mixed"),
  };
  const table = (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr style={{ color: t.axis }}>
          <th className="pr-3">Pick</th>
          <th className="pr-3">Story</th>
          <th className="pr-3">{xLabel}</th>
          <th className="pr-3">{yLabel}</th>
        </tr>
      </thead>
      <tbody>
        {points.map((p) => (
          <tr key={`${p.label}-${p.x}-${p.y}`} style={{ color: t.text }}>
            <td className="pr-3">{p.note ? `${p.label} (${p.note})` : p.label}</td>
            <td className="pr-3">{p.story ?? "Mixed story"}</td>
            <td className="pr-3">{p.x}</td>
            <td className="pr-3">{p.y}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <ChartFrame title={title} height={height} table={table}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
        <CartesianGrid stroke={t.grid} />
        <XAxis
          type="number"
          dataKey="x"
          name={xLabel}
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          label={{ value: xLabel, position: "insideBottom", offset: -8, fill: t.axis, fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name={yLabel}
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          width={44}
        />
        <ZAxis range={[60, 60]} />
        <ReferenceLine x={0} stroke={t.borderStrong} />
        <ReferenceLine y={0} stroke={t.borderStrong} />
        <Tooltip content={quadrantTooltip} cursor={{ stroke: t.grid }} />
        <Scatter name="value that hit" data={byTone.value_hit} fill={colors.value_hit} isAnimationActive={false} />
        <Scatter name="reach that busted" data={byTone.reach_bust} fill={colors.reach_bust} isAnimationActive={false} />
        <Scatter name="reach that hit" data={byTone.reach_hit} fill={colors.reach_hit} isAnimationActive={false} />
        <Scatter name="value that missed" data={byTone.value_miss} fill={colors.value_miss} isAnimationActive={false} />
        <Scatter name="mixed story" data={byTone.mixed} fill={colors.mixed} isAnimationActive={false} />
      </ScatterChart>
    </ChartFrame>
  );
}

// ── Beeswarm / strip ─────────────────────────────────────────────────────────
// One horizontal strip per group (e.g. a team's weekly scores) with deterministic
// jitter so the spread — boom/bust vs steady — reads at a glance.
function beeTooltip({
  active,
  payload,
}: TooltipProps<number | string, string>): React.ReactElement | null {
  if (!active || !payload?.length) return null;
  const t = chartTheme();
  const p = payload[0]?.payload as { group: string; x: number } | undefined;
  if (!p) return null;
  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.borderStrong}`,
        borderRadius: 10,
        fontFamily: t.fontMono,
        fontSize: 12,
        padding: "6px 9px",
        color: t.text,
      }}
    >
      {p.group}: {p.x}
    </div>
  );
}

export function Beeswarm({
  groups,
  title,
  xLabel = "Value",
  height,
}: {
  groups: { label: string; values: number[] }[];
  title: string;
  xLabel?: string;
  height?: number;
}) {
  const t = chartTheme();
  const points: { x: number; y: number; group: string }[] = [];
  groups.forEach((g, gi) => {
    g.values.forEach((v, vi) => {
      const seed = Math.sin(v * 12.9898 + gi * 7.13 + vi * 3.7) * 43758.5453;
      const jitter = (seed - Math.floor(seed)) * 0.6 - 0.3;
      points.push({ x: v, y: gi + jitter, group: g.label });
    });
  });
  const h = height ?? Math.max(180, groups.length * 34 + 60);
  const longest = Math.max(8, ...groups.map((g) => g.label.length));
  const groupColor = (label: string) => seriesColor(groups.findIndex((g) => g.label === label));
  const r1 = (n: number) => Math.round(n * 10) / 10;
  const table = (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr style={{ color: t.axis }}>
          <th className="pr-3">Group</th>
          <th className="pr-3">n</th>
          <th className="pr-3">min</th>
          <th className="pr-3">max</th>
          <th className="pr-3">avg</th>
        </tr>
      </thead>
      <tbody>
        {groups.map((g) => {
          const n = g.values.length;
          const avg = n ? g.values.reduce((s, v) => s + v, 0) / n : 0;
          return (
            <tr key={g.label} style={{ color: t.text }}>
              <td className="pr-3">{g.label}</td>
              <td className="pr-3">{n}</td>
              <td className="pr-3">{n ? r1(Math.min(...g.values)) : "—"}</td>
              <td className="pr-3">{n ? r1(Math.max(...g.values)) : "—"}</td>
              <td className="pr-3">{n ? r1(avg) : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
  return (
    <ChartFrame title={title} height={h} table={table}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 8 }}>
        <CartesianGrid stroke={t.grid} />
        <XAxis
          type="number"
          dataKey="x"
          name={xLabel}
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          label={{ value: xLabel, position: "insideBottom", offset: -8, fill: t.axis, fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          width={Math.min(150, longest * 7 + 12)}
          reversed
          domain={[-0.5, groups.length - 0.5]}
          ticks={groups.map((_, i) => i)}
          tickFormatter={(v: number) => groups[v]?.label ?? ""}
        />
        <ZAxis range={[50, 50]} />
        <Tooltip content={beeTooltip} cursor={{ stroke: t.grid }} />
        <Scatter data={points} isAnimationActive={false}>
          {points.map((p, i) => (
            <Cell key={i} fill={groupColor(p.group)} />
          ))}
        </Scatter>
      </ScatterChart>
    </ChartFrame>
  );
}

// ── Margin line (the shape of a rivalry) ─────────────────────────────────────
// Signed margin across a sequence (every meeting), zero line in the middle: wins
// above (green), losses below (red); a championship meeting gets a gold ring.
export function MarginLine({
  points,
  title,
  xLabel = "Meeting",
  height = 240,
}: {
  points: { label: string; margin: number; championship?: boolean; note?: string }[];
  title: string;
  xLabel?: string;
  height?: number;
}) {
  const t = chartTheme();
  const rows: ChartRow[] = points.map((p) => ({ label: p.label, margin: p.margin, __note: p.note ?? "" }));
  const series: SeriesDef[] = [{ key: "margin", label: "Margin" }];
  function MarginDot({ cx, cy, index }: { cx?: number; cy?: number; index?: number }) {
    if (cx == null || cy == null || index == null) return <g key={`m-${index}`} />;
    const p = points[index];
    const champ = !!p?.championship;
    const positive = (p?.margin ?? 0) >= 0;
    return (
      <g key={`m-${index}`}>
        <circle cx={cx} cy={cy} r={champ ? 6 : 3.5} fill={positive ? t.win : t.loss} stroke={champ ? t.gold : "none"} strokeWidth={champ ? 2 : 0} />
        {champ && <title>{`Championship · ${p?.label}`}</title>}
      </g>
    );
  }
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={rows} series={series} xKey="label" xLabel={xLabel} />}>
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="label" stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis stroke={t.axis} tick={axisTick()} tickLine={false} width={40} />
        <Tooltip {...tooltipProps()} />
        <ReferenceLine y={0} stroke={t.borderStrong} />
        <Line type="monotone" dataKey="margin" name="Margin" stroke={seriesColor(0)} strokeWidth={2} dot={MarginDot} isAnimationActive={false} />
      </LineChart>
    </ChartFrame>
  );
}

// ── Metric scatter (two-axis quadrant) ───────────────────────────────────────
// A neutral two-axis scatter with zero reference lines (pass already-centered
// deltas). Used e.g. for manager efficiency vs scoring; the draft-specific
// ScatterQuadrant keeps its own value/reach wording.
function metricTooltip(xLabel: string, yLabel: string) {
  return function MetricTip({
    active,
    payload,
  }: TooltipProps<number | string, string>): React.ReactElement | null {
    if (!active || !payload?.length) return null;
    const t = chartTheme();
    const p = payload[0]?.payload as { label: string; x: number; y: number; note?: string } | undefined;
    if (!p) return null;
    return (
      <div
        style={{
          background: t.surface,
          border: `1px solid ${t.borderStrong}`,
          borderRadius: 10,
          fontFamily: t.fontMono,
          fontSize: 12,
          padding: "8px 10px",
          color: t.text,
        }}
      >
        <div style={{ marginBottom: 4 }}>{p.label}</div>
        {p.note && <div style={{ color: t.axis, marginBottom: 4 }}>{p.note}</div>}
        <div>
          {xLabel}: {p.x > 0 ? "+" : ""}
          {p.x} · {yLabel}: {p.y > 0 ? "+" : ""}
          {p.y}
        </div>
      </div>
    );
  };
}

export function MetricScatter({
  points,
  title,
  xLabel,
  yLabel,
  height = 300,
}: {
  points: { x: number; y: number; label: string; note?: string }[];
  title: string;
  xLabel: string;
  yLabel: string;
  height?: number;
}) {
  const t = chartTheme();
  // Quadrant tone: top-right (good on both) gold, bottom-left loss, else neutral.
  const toneColor = (p: { x: number; y: number }) =>
    p.x >= 0 && p.y >= 0 ? t.gold : p.x < 0 && p.y < 0 ? t.loss : seriesColor(1);
  const table = (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr style={{ color: t.axis }}>
          <th className="pr-3">Entry</th>
          <th className="pr-3">{xLabel}</th>
          <th className="pr-3">{yLabel}</th>
        </tr>
      </thead>
      <tbody>
        {points.map((p) => (
          <tr key={p.label} style={{ color: t.text }}>
            <td className="pr-3">{p.note ? `${p.label} (${p.note})` : p.label}</td>
            <td className="pr-3">{p.x}</td>
            <td className="pr-3">{p.y}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <ChartFrame title={title} height={height} table={table}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
        <CartesianGrid stroke={t.grid} />
        <XAxis
          type="number"
          dataKey="x"
          name={xLabel}
          stroke={t.axis}
          tick={axisTick()}
          tickLine={false}
          label={{ value: xLabel, position: "insideBottom", offset: -8, fill: t.axis, fontSize: 11 }}
        />
        <YAxis type="number" dataKey="y" name={yLabel} stroke={t.axis} tick={axisTick()} tickLine={false} width={44} />
        <ZAxis range={[60, 60]} />
        <ReferenceLine x={0} stroke={t.borderStrong} />
        <ReferenceLine y={0} stroke={t.borderStrong} />
        <Tooltip content={metricTooltip(xLabel, yLabel)} cursor={{ stroke: t.grid }} />
        <Scatter data={points} isAnimationActive={false}>
          {points.map((p, i) => (
            <Cell key={i} fill={toneColor(p)} />
          ))}
        </Scatter>
      </ScatterChart>
    </ChartFrame>
  );
}
