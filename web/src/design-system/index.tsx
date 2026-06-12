import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { useState } from "react";

import { initials, record } from "@/lib/format";

// The durable primitive layer. Pages compose these; they hold no business logic.
// Styling lives in styles/global.css (the `dz-*` classes) reading tokens.css.

export function Card({
  children,
  className = "",
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <section className={`dz-card ${hover ? "dz-card--hover" : ""} ${className}`}>{children}</section>
  );
}

export function CardHeader({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return (
    <header className="flex items-center justify-between gap-3 border-b border-[var(--hairline)] px-5 py-4">
      <div>
        {eyebrow && <div className="dz-eyebrow mb-1">{eyebrow}</div>}
        <h2 className="font-display text-[22px] font-bold uppercase leading-none tracking-wide text-text">
          {title}
        </h2>
      </div>
      {action}
    </header>
  );
}

export function Stat({
  label,
  value,
  unit,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: "default" | "win" | "loss" | "accent";
}) {
  const color =
    tone === "win"
      ? "text-win"
      : tone === "loss"
        ? "text-loss"
        : tone === "accent"
          ? "text-accent"
          : "text-text";
  // Big stat numbers use the display face (jersey-number energy), per the handoff;
  // tabular mono is reserved for table cells and inline scores.
  return (
    <div>
      <div className="dz-eyebrow mb-1">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className={`font-display text-[30px] font-bold leading-none tracking-wide ${color}`}>{value}</span>
        {unit && <span className="font-mono text-[var(--fs-sm)] text-muted">{unit}</span>}
      </div>
    </div>
  );
}

export function Button({
  children,
  variant = "secondary",
  loading = false,
  className = "",
  disabled,
  ...props
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const mod = variant === "primary" ? "dz-btn--primary" : variant === "ghost" ? "dz-btn--ghost" : "";
  return (
    <button
      type="button"
      className={`dz-btn ${mod} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <span className="dz-live-dot" aria-hidden />}
      {children}
    </button>
  );
}

export function Checkbox({
  label,
  hint,
  className = "",
  ...props
}: {
  label: ReactNode;
  hint?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  return (
    <label className={`dz-checkbox ${className}`.trim()}>
      <input type="checkbox" className="dz-checkbox__box" {...props} />
      <span className="dz-checkbox__label">{label}</span>
      {hint && <span className="dz-checkbox__hint">{hint}</span>}
    </label>
  );
}

export function Badge({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: "default" | "accent" | "win" | "loss" | "gap";
}) {
  const mod =
    variant === "accent"
      ? "dz-badge--accent"
      : variant === "win"
        ? "dz-badge--win"
        : variant === "loss"
          ? "dz-badge--loss"
          : variant === "gap"
            ? "dz-badge--gap"
            : "";
  return <span className={`dz-badge ${mod}`.trim()}>{children}</span>;
}

export function Pill({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "accent" | "win" | "loss";
}) {
  const mod =
    tone === "accent"
      ? "dz-pill--accent"
      : tone === "win"
        ? "dz-pill--win"
        : tone === "loss"
          ? "dz-pill--loss"
          : "";
  return <span className={`dz-pill ${mod}`.trim()}>{children}</span>;
}

export function RecordLine({ wins, losses, ties }: { wins: number; losses: number; ties: number }) {
  return (
    <span className="dz-record">
      <span className="text-win">{wins}</span>
      <span className="text-faint">-</span>
      <span className="text-loss">{losses}</span>
      {ties > 0 && (
        <>
          <span className="text-faint">-</span>
          <span className="text-muted">{ties}</span>
        </>
      )}
    </span>
  );
}

export function Chip({
  name,
  sub,
  size = "md",
  avatarUrl,
}: {
  name: string | null | undefined;
  sub?: string;
  size?: "md" | "lg";
  /** Team-logo URL (e.g. `/v1/teams/{id}/avatar`). Falls back to the name
   *  monogram when absent or when the image fails to load / 404s (Q11). */
  avatarUrl?: string | null;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const avatarClass = `dz-avatar ${size === "lg" ? "dz-avatar--lg" : ""}`.trim();
  const showImg = Boolean(avatarUrl) && !imgFailed;
  return (
    <span className="inline-flex items-center gap-3">
      {showImg ? (
        <img
          className={`${avatarClass} dz-avatar--img`}
          src={avatarUrl as string}
          alt=""
          loading="lazy"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <span className={avatarClass}>{initials(name)}</span>
      )}
      <span className="flex flex-col leading-tight">
        <span className="font-semibold text-text">{name ?? "—"}</span>
        {sub && <span className="text-[var(--fs-xs)] text-faint">{sub}</span>}
      </span>
    </span>
  );
}

/** One warm, consistent sentence for a season whose per-player fantasy scoring
 *  isn't available, reused across every view so the affordance reads identically
 *  (F-33). The gap is data-driven on the per-season `is_scored` flag — with the
 *  pre-2016 reconstruction landed (F-51) the only unscored season is normally the
 *  current, in-progress one, so the copy is year-agnostic and makes no claim
 *  about team-data completeness (which is partial while a season is live). */
export const UNSCORED_SEASON_NOTE =
  "Per-player fantasy scoring isn't available for this season yet — values that depend on it show a gap marker, never a zero.";

/** The honesty component: shown wherever a metric is absent. Never a fake 0.
 *  Renders the dashed + hatched affordance with an amber diamond (drawn in CSS). */
export function DataGap({ reason, size = "md" }: { reason?: string; size?: "md" | "sm" }) {
  const labels: Record<string, string> = {
    season_unscored: "Per-player scoring not available for this season",
    no_scored_data: "No scored data for this scope",
    availability_history_not_reconstructable: "Availability — current season only",
    no_availability_rows: "No availability snapshots",
    no_meetings: "These managers never met",
    team_defense_not_scored: "Team defense not scored (known gap)",
    draft_not_captured: "Draft not captured for this season",
    player_unscored: "Player not scored — value unavailable",
    insufficient_history: "Not enough draft history to value this slot",
    player_bio_unavailable: "Biographical data unavailable",
    unscored_tenure:
      "This player's rostered seasons have no per-player fantasy scoring available; their team/roster data is intact",
    bracket_unavailable: "Bracket data isn't available for this season",
    consolation_indistinguishable:
      "Consolation bracket can't be separated from the playoff bracket for this season",
    conference_membership_unavailable:
      "Conference membership data for historical seasons is not yet available",
    roster_history_unavailable:
      "Week-by-week roster history isn't available for this season, so adds and drops can't be derived",
  };
  return (
    <span className={`dz-datagap ${size === "sm" ? "dz-datagap--sm" : ""}`.trim()} role="note">
      {labels[reason ?? ""] ?? reason ?? "Data not available"}
    </span>
  );
}

/** Championship / podium marker for trophy cases. */
export function Trophy({ label, count }: { label?: string; count?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[var(--fs-sm)] text-accent" title={label}>
      <span aria-hidden>★</span>
      {count != null && <span className="num">{count}</span>}
      {label && <span className="text-muted">{label}</span>}
    </span>
  );
}

/** Prev/next week control. The bound value lives in the URL at the page level. */
export function WeekStepper({
  week,
  min = 1,
  max,
  onChange,
}: {
  week: number;
  min?: number;
  max: number;
  onChange: (week: number) => void;
}) {
  const weeks = Array.from({ length: Math.max(0, max - min + 1) }, (_, i) => min + i);
  return (
    <div className="inline-flex items-center gap-2" role="group" aria-label="Week">
      <Button
        variant="ghost"
        aria-label="Previous week"
        disabled={week <= min}
        onClick={() => onChange(week - 1)}
      >
        ‹
      </Button>
      <label className="sr-only" htmlFor="week-stepper-select">
        Select week
      </label>
      <select
        id="week-stepper-select"
        className="dz-select num w-[5.75rem] py-1 text-[var(--fs-sm)]"
        aria-label="Select week"
        value={week}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {weeks.map((w) => (
          <option key={w} value={w}>
            Wk {w}
          </option>
        ))}
      </select>
      <Button
        variant="ghost"
        aria-label="Next week"
        disabled={week >= max}
        onClick={() => onChange(week + 1)}
      >
        ›
      </Button>
    </div>
  );
}

/** Within-page section switching. */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="inline-flex gap-1 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-1)] p-1">
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            className={[
              "rounded-[var(--radius-sm)] px-3 py-1.5 text-[var(--fs-sm)] font-medium transition-colors",
              active ? "bg-[var(--accent-soft)] text-accent" : "text-muted hover:text-text",
            ].join(" ")}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

/** Inline SVG sparkline (PF trajectory etc.). Decorative — pair with a real number. */
export function Sparkline({
  values,
  width = 96,
  height = 32,
  stroke = "var(--accent)",
  className = "",
}: {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
  className?: string;
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      className={className}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="trend sparkline"
      preserveAspectRatio="none"
    >
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--surface-2)] ${className}`} />;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="grid place-items-center gap-2 p-10 text-center">
      <div className="font-display text-[var(--fs-h3)] uppercase tracking-wide text-muted">{title}</div>
      {hint && <div className="text-[var(--fs-sm)] text-faint">{hint}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="grid place-items-center gap-3 p-10 text-center">
      <div className="dz-eyebrow text-loss">Signal lost</div>
      <div className="text-[var(--fs-sm)] text-muted">{message}</div>
      {onRetry && (
        <Button variant="primary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export { record };
