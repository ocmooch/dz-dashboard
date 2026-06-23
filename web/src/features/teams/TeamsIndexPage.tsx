import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useSeasons } from "@/app/shell/SeasonContext";
import {
  Card,
  Chip,
  ErrorState,
  RecordLine,
  Skeleton,
  Tabs,
  Trophy,
} from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { ordinal, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type TeamRow = components["schemas"]["TeamsIndexRow"];
type GroupBy = "season" | "owner";

async function fetchTeams(): Promise<TeamRow[]> {
  const { data, error } = await api.GET("/v1/teams");
  if (error || !data) throw new Error("Failed to load teams");
  return data.data.teams;
}

/** A collapsible section — the accordion unit for either grouping. */
function Section({
  title,
  meta,
  open,
  onToggle,
  children,
}: {
  title: string;
  meta?: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left hover:text-accent"
      >
        <span className="flex items-baseline gap-3">
          <span className="font-display text-[var(--fs-h3)] font-bold tracking-wide">{title}</span>
          {meta && <span className="text-[var(--fs-xs)] text-faint">{meta}</span>}
        </span>
        <span className="num text-muted">{open ? "–" : "+"}</span>
      </button>
      {open && <div className="border-t border-[var(--hairline)]">{children}</div>}
    </Card>
  );
}

/** One team's row inside a section — links to the team page. */
function TeamRowItem({ t, showSeason }: { t: TeamRow; showSeason: boolean }) {
  const sub = showSeason
    ? (t.season_year != null ? `${t.season_year}` : undefined)
    : (t.owner_name ?? undefined);
  return (
    <Link
      to={`/teams/${t.team_id}`}
      className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-[var(--surface-2)]"
    >
      <div className="flex items-center gap-3">
        <Chip name={t.team_name ?? t.owner_name} sub={sub} avatarUrl={teamAvatarUrl(t.team_id)} />
        {t.is_champion ? (
          <Trophy label="Champion" />
        ) : t.final_rank != null && t.final_rank <= 3 ? (
          <span className="text-[var(--fs-xs)] text-faint">{ordinal(t.final_rank)}</span>
        ) : null}
      </div>
      <RecordLine wins={t.wins} losses={t.losses} ties={t.ties} />
    </Link>
  );
}

export function TeamsIndexPage() {
  const { current } = useSeasons();
  const [groupBy, setGroupBy] = useState<GroupBy>("season");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.teams,
    queryFn: fetchTeams,
  });

  // Build ordered groups for the active grouping. By season: newest first. By
  // owner: alphabetical, each owner's teams newest-season first.
  const groups = useMemo(() => {
    const rows = data ?? [];
    const out = new Map<string, { title: string; meta?: string; rows: TeamRow[] }>();
    if (groupBy === "season") {
      for (const t of rows) {
        const key = String(t.season_year ?? "—");
        if (!out.has(key)) out.set(key, { title: key, rows: [] });
        out.get(key)!.rows.push(t);
      }
    } else {
      const byOwner = [...rows].sort(
        (a, b) =>
          (a.owner_name ?? "").localeCompare(b.owner_name ?? "") ||
          (b.season_year ?? 0) - (a.season_year ?? 0),
      );
      for (const t of byOwner) {
        const key = String(t.owner_id);
        if (!out.has(key)) out.set(key, { title: t.owner_name ?? "Unknown", rows: [] });
        out.get(key)!.rows.push(t);
      }
    }
    for (const g of out.values()) g.meta = `${g.rows.length} team${g.rows.length === 1 ? "" : "s"}`;
    return [...out.entries()].map(([key, g]) => ({ key, ...g }));
  }, [data, groupBy]);

  // Open sections, namespaced per grouping so each remembers its own state.
  // Seed once with the current season open (by-owner starts fully collapsed —
  // the owner list is long). Seeding waits for the season context to load.
  const [open, setOpen] = useState<Set<string>>(new Set());
  const seeded = useRef(false);
  useEffect(() => {
    if (!seeded.current && current?.season_year != null) {
      seeded.current = true;
      setOpen(new Set([`season:${current.season_year}`]));
    }
  }, [current]);
  const nk = (key: string) => `${groupBy}:${key}`;
  const isOpen = (key: string) => open.has(nk(key));
  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(nk(key))) next.delete(nk(key));
      else next.add(nk(key));
      return next;
    });

  return (
    <div className="dz-rise space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="dz-eyebrow mb-1">League</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Teams</h1>
        </div>
        <Tabs<GroupBy>
          tabs={[
            { id: "season", label: "By season" },
            { id: "owner", label: "By owner" },
          ]}
          value={groupBy}
          onChange={setGroupBy}
        />
      </div>

      {isLoading && <Skeleton className="h-64 w-full" />}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data &&
        groups.map((g) => (
          <Section
            key={`${groupBy}-${g.key}`}
            title={g.title}
            meta={g.meta}
            open={isOpen(g.key)}
            onToggle={() => toggle(g.key)}
          >
            <div className="divide-y divide-[var(--hairline)]">
              {g.rows.map((t) => (
                <TeamRowItem key={t.team_id} t={t} showSeason={groupBy === "owner"} />
              ))}
            </div>
          </Section>
        ))}
    </div>
  );
}
