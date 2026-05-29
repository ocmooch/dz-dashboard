import type { ReactNode } from "react";

import { initials, record } from "@/lib/format";

// The durable primitive layer. Pages compose these; they hold no business logic.

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
    <header className="flex items-end justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
      <div>
        {eyebrow && <div className="dz-eyebrow mb-1">{eyebrow}</div>}
        <h2 className="font-display text-[var(--fs-h3)] font-semibold tracking-wide text-text">{title}</h2>
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
  return (
    <div>
      <div className="dz-eyebrow mb-1">{label}</div>
      <div className={`num text-[var(--fs-h1)] font-semibold leading-none ${color}`}>
        {value}
        {unit && <span className="ml-1 text-[var(--fs-sm)] text-faint">{unit}</span>}
      </div>
    </div>
  );
}

export function Badge({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: "default" | "accent" | "gap";
}) {
  const cls = variant === "accent" ? "dz-badge dz-badge--accent" : variant === "gap" ? "dz-badge dz-badge--gap" : "dz-badge";
  return <span className={cls}>{children}</span>;
}

export function RecordLine({ wins, losses, ties }: { wins: number; losses: number; ties: number }) {
  return (
    <span className="num">
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

export function Chip({ name, sub }: { name: string | null | undefined; sub?: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="grid h-7 w-7 place-items-center rounded-full border border-[var(--border)] bg-[var(--surface-2)] font-mono text-[var(--fs-xs)] uppercase text-muted">
        {initials(name)}
      </span>
      <span className="flex flex-col leading-tight">
        <span className="font-medium text-text">{name ?? "—"}</span>
        {sub && <span className="text-[var(--fs-xs)] text-faint">{sub}</span>}
      </span>
    </span>
  );
}

/** The honesty component: shown wherever a metric is absent. Never a fake 0. */
export function DataGap({ reason }: { reason?: string }) {
  const labels: Record<string, string> = {
    season_unscored: "Not scored — pre-2016 season",
    no_scored_data: "No scored data for this scope",
    availability_history_not_reconstructable: "Availability — current season only",
    no_availability_rows: "No availability snapshots",
    no_meetings: "These managers never met",
    team_defense_not_scored: "Team defense not scored (known gap)",
  };
  return (
    <span className="dz-badge dz-badge--gap" role="note">
      <span aria-hidden>▲</span>
      {labels[reason ?? ""] ?? reason ?? "Data not available"}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--surface-2)] ${className}`} />;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="grid place-items-center gap-2 p-10 text-center">
      <div className="font-display text-[var(--fs-h3)] text-muted">{title}</div>
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
        <button
          onClick={onRetry}
          className="dz-badge dz-badge--accent cursor-pointer"
          type="button"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export { record };
