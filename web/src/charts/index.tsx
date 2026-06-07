import type { ReactNode } from "react";
import {
  type TooltipProps,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartTheme, heatColor, seriesColor, tooltipProps } from "./chartTheme";

// Thin, theme-bound wrappers over Recharts (and a CSS-grid Heatmap). Every chart
// carries an accessible title and a <details> data-table fallback so meaning
// survives without color or sight. Pages pass already-computed data — no logic here.

export type ChartRow = Record<string, number | string | null>;
export type SeriesDef = { key: string; label: string; color?: string };

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
export function BarCompare({ data, series, xKey, xLabel = xKey, title, height }: CartesianProps) {
  const t = chartTheme();
  return (
    <ChartFrame title={title} height={height} table={<DataTable data={data} series={series} xKey={xKey} xLabel={xLabel} />}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey={xKey} stroke={t.axis} tick={axisTick()} tickLine={false} />
        <YAxis stroke={t.axis} tick={axisTick()} tickLine={false} width={40} />
        <Tooltip {...tooltipProps()} cursor={{ fill: t.grid, opacity: 0.4 }} />
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color ?? seriesColor(i)} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        ))}
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

/** standings-over-time as a bump/rank chart — one line per team, rank 1 on top. */
export function RankFlow({
  data,
  series,
  xKey,
  xLabel = xKey,
  title,
  height,
  teamCount,
}: CartesianProps & { teamCount: number }) {
  const t = chartTheme();
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
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ChartFrame>
  );
}

/** rivalry win-pct matrix. Plain CSS grid (per the handoff), not Recharts.
 *  values[r][c] = row owner's win-pct vs col owner (0–100); null = never met /
 *  pre-coverage → a hatched DataGap cell showing "—", never 0. */
export function Heatmap({
  rows,
  cols,
  values,
  title,
  selected,
  onSelect,
}: {
  rows: string[];
  cols: string[];
  values: (number | null)[][];
  title: string;
  selected?: { r: number; c: number } | null;
  onSelect?: (r: number, c: number) => void;
}) {
  const template = `minmax(64px, 1fr) repeat(${cols.length}, minmax(28px, 1fr))`;
  return (
    <figure className="m-0 overflow-x-auto" aria-label={title}>
      <figcaption className="sr-only">{title}</figcaption>
      <div role="grid" className="grid gap-px" style={{ gridTemplateColumns: template, minWidth: cols.length * 32 + 64 }}>
        <div role="columnheader" aria-hidden />
        {cols.map((c) => (
          <div key={c} role="columnheader" className="truncate p-1 text-center font-mono text-[10px] uppercase text-faint">
            {c}
          </div>
        ))}
        {rows.map((rowName, r) => (
          <div key={rowName} role="row" className="contents">
            <div role="rowheader" className="truncate p-1 text-right font-mono text-[11px] text-muted">
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
                    className="dz-datagap grid place-items-center rounded-none border-0 p-0 text-[10px]"
                    style={{ minHeight: 28 }}
                  >
                    —
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
