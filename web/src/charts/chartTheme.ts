// The single bridge between the CSS design tokens and Recharts. Charts read
// resolved token values here so they match the theme and re-skin for free when
// tokens change. Fallbacks mirror tokens.css so charts still render correctly in
// tests / before fonts load.

const FALLBACK = {
  axis: "#5f6b7c", // --text-faint
  grid: "#1f2630", // --hairline
  text: "#9aa7b8", // --text-muted
  surface: "#12161d", // --surface-1
  borderStrong: "#36404e", // --border-strong
  mono: "IBM Plex Mono, ui-monospace, monospace",
};

const SERIES_FALLBACK = ["#ff6a1a", "#5aa9ff", "#34d39e", "#f5b73d", "#b07cff", "#ff8fa3"];

function readVar(name: string, fallback: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export type ChartTheme = {
  axis: string;
  grid: string;
  text: string;
  surface: string;
  borderStrong: string;
  fontMono: string;
  series: string[];
};

export function chartTheme(): ChartTheme {
  return {
    axis: readVar("--text-faint", FALLBACK.axis),
    grid: readVar("--hairline", FALLBACK.grid),
    text: readVar("--text-muted", FALLBACK.text),
    surface: readVar("--surface-1", FALLBACK.surface),
    borderStrong: readVar("--border-strong", FALLBACK.borderStrong),
    fontMono: readVar("--font-mono", FALLBACK.mono),
    series: SERIES_FALLBACK.map((fb, i) => readVar(`--series-${i + 1}`, fb)),
  };
}

/** Categorical color for series index i (wraps the 6-color ramp). */
export function seriesColor(i: number): string {
  const s = chartTheme().series;
  return s[i % s.length];
}

/** Tooltip styling shared by every chart wrapper (mono numbers on a surface card). */
export function tooltipProps() {
  const t = chartTheme();
  return {
    contentStyle: {
      background: t.surface,
      border: `1px solid ${t.borderStrong}`,
      borderRadius: 10,
      fontFamily: t.fontMono,
      fontSize: 12,
    },
    labelStyle: { color: t.text },
    itemStyle: { color: t.text },
  } as const;
}

/** Heatmap interpolation loss(red) → steel → win(green), matching the rivalry
 *  matrix in the design (heatColor in app.js). `pct` is 0–100. */
export function heatColor(pct: number): string {
  const loss = [239, 71, 97];
  const steel = [57, 65, 78];
  const win = [52, 211, 158];
  const t = Math.max(0, Math.min(100, pct)) / 100;
  const [a, b] = t < 0.5 ? [loss, steel] : [steel, win];
  const k = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
  const ch = (i: number) => Math.round(a[i] + (b[i] - a[i]) * k);
  return `rgb(${ch(0)}, ${ch(1)}, ${ch(2)})`;
}
