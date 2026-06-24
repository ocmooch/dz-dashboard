import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { LineTrend } from "@/charts";
import { InjuryBadge } from "@/components/InjuryBadge";
import { PlayerScoreCell } from "@/components/PlayerScoreCell";
import { ResultTimeline } from "@/features/teams/ResultTimeline";
import {
  Badge,
  Card,
  CardHeader,
  Chip,
  DataGap,
  EmptyState,
  ErrorState,
  UNSCORED_SEASON_NOTE,
  Pill,
  RecordLine,
  Sacko,
  Skeleton,
  Stat,
  Trophy,
  WeekStepper,
} from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type OwnerSeasonRow = components["schemas"]["OwnerSeasonRow"];
type TeamTransaction = components["schemas"]["TeamTransaction"];

async function fetchOverview(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load team");
  return data.data;
}

async function fetchRoster(id: number, week: number | null) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/roster", {
    params: { path: { team_id: id }, query: { week: week ?? undefined } },
  });
  if (error || !data) throw new Error("Failed to load roster");
  return data.data;
}

async function fetchSchedule(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/schedule", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load schedule");
  return data.data;
}

async function fetchScoringTrend(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/scoring-trend", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load scoring trend");
  return data.data;
}

async function fetchTransactions(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/transactions", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load transactions");
  return data.data;
}

async function fetchRosterMoves(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/roster-moves", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load roster moves");
  return data.data;
}

async function fetchFaabBudget(id: number) {
  const { data, error } = await api.GET("/v1/teams/{team_id}/faab-budget", {
    params: { path: { team_id: id } },
  });
  if (error || !data) throw new Error("Failed to load FAAB budget");
  return data.data;
}

async function fetchOwnerSeasons(ownerId: number): Promise<OwnerSeasonRow[]> {
  const { data, error } = await api.GET("/v1/owners/{owner_id}/seasons", {
    params: { path: { owner_id: ownerId } },
  });
  if (error || !data) throw new Error("Failed to load owner seasons");
  return data.data.seasons;
}

function RosterCard({ teamId }: { teamId: number }) {
  const [params, setParams] = useSearchParams();
  const weekParam = params.get("week");
  const week = weekParam == null ? null : Math.max(1, Number(weekParam) || 1);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.teamRoster(teamId, week),
    queryFn: () => fetchRoster(teamId, week),
  });

  const weeks = data?.weeks_available ?? [];
  const minWeek = weeks[0] ?? 1;
  const maxWeek = weeks[weeks.length - 1] ?? 1;
  const activeWeek = data?.week ?? week ?? maxWeek;

  const setWeek = (w: number) => {
    const next = new URLSearchParams(params);
    next.set("week", String(w));
    setParams(next, { replace: true });
  };

  return (
    <Card>
      <CardHeader
        eyebrow={`week ${activeWeek}`}
        title="Roster"
        action={
          weeks.length > 1 ? (
            <WeekStepper week={activeWeek} min={minWeek} max={maxWeek} onChange={setWeek} />
          ) : undefined
        }
      />
      {isLoading && (
        <div className="space-y-2 p-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      )}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}
      {data && data.players.length === 0 && (
        <EmptyState title="No roster recorded" hint="No roster snapshot for this week." />
      )}
      {data?.roster_reconstructed && data.roster_reconstructed_note && (
        <div className="px-5 pt-2">
          <div
            className="rounded border border-[color:var(--hairline)] bg-[color:var(--surface-2)] px-3 py-2 text-[var(--fs-xs)] text-muted"
            role="note"
          >
            <span className="dz-eyebrow mr-1 text-faint">reconstructed</span>
            {data.roster_reconstructed_note}
          </div>
        </div>
      )}
      {data && data.players.length > 0 && (
        <div className="overflow-x-auto">
          <table className="dz-table">
            <thead>
              <tr>
                <th>Slot</th>
                <th>Player</th>
                <th>Pos</th>
                <th className="dz-num">Points</th>
              </tr>
            </thead>
            <tbody>
              {data.players.map((p) =>
                p.is_empty ? (
                  // An open roster spot at week-end — fully dashed, no link. The
                  // nearby transactions show the drop that left it empty.
                  <tr key={p.player_id} className="text-faint opacity-50">
                    <td className="font-mono text-[var(--fs-xs)]">—</td>
                    <td>empty slot</td>
                    <td>—</td>
                    <td className="dz-num">—</td>
                  </tr>
                ) : (
                  <tr key={p.player_id} className={p.is_starter ? "" : "opacity-70"}>
                    <td className="font-mono text-[var(--fs-xs)] text-muted">
                      {p.roster_slot ?? "—"}
                    </td>
                    <td>
                      <Link to={`/players/${p.player_id}`} className="hover:text-accent">
                        <Chip name={p.player_name} sub={p.nfl_team ?? undefined} />
                      </Link>
                      {p.injury_status != null && (
                        <InjuryBadge
                          status={p.injury_status}
                          bodyPart={p.injury_body_part}
                          secondary={p.injury_secondary}
                          practiceStatus={p.injury_practice_status}
                        />
                      )}
                    </td>
                    <td className="text-muted">{p.position ?? "—"}</td>
                    <td className="dz-num">
                      {p.league_points == null ? (
                        <DataGap reason={data.is_scored ? "no_scored_data" : "season_unscored"} size="sm" />
                      ) : (
                        <PlayerScoreCell
                          points={p.league_points}
                          zeroReason={p.zero_reason}
                          zeroDetail={p.zero_detail}
                          zeroLabel={["Bye", "DNP", "Out"].includes(p.context_label ?? "") ? p.context_label : undefined}
                          injuryBodyPart={p.injury_body_part}
                          muted={!p.is_starter}
                        />
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function ScheduleCard({ teamId, boxScoresAvailable }: { teamId: number; boxScoresAvailable: boolean }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.teamSchedule(teamId),
    queryFn: () => fetchSchedule(teamId),
  });
  return (
    <Card>
      <CardHeader eyebrow="results" title="Schedule" />
      {isLoading && <Skeleton className="m-5 h-40" />}
      {data && data.games.length === 0 && <EmptyState title="No games scheduled" />}
      {data && data.games.length > 0 && (
        <>
          <div className="px-5 pb-3 pt-1">
            <ResultTimeline games={data.games} />
          </div>
          <ol className="divide-y divide-[var(--hairline)] border-t border-[var(--hairline)]">
            {data.games.map((g) => {
              const tone =
                g.result === "W" ? "text-win" : g.result === "L" ? "text-loss" : "text-muted";
              return (
                <li
                  key={g.matchup_id}
                  className="flex items-center gap-2 px-5 py-1.5 text-[var(--fs-sm)]"
                >
                  <span className={`num w-4 font-bold ${tone}`}>{g.result ?? "—"}</span>
                  <span className="num w-10 text-faint">wk {g.week}</span>
                  <Link
                    to={boxScoresAvailable ? `/matchups/${g.matchup_id}` : `/matchups?week=${g.week}`}
                    className="flex-1 truncate text-text hover:text-accent"
                  >
                    vs {g.opponent_team_name ?? g.opponent_owner_name ?? "Bye"}
                  </Link>
                  {g.is_playoff && (
                    <span className="dz-eyebrow text-[color:var(--accent)]">PO</span>
                  )}
                  <span className="num shrink-0">
                    <span className={tone}>{num(g.team_score)}</span>
                    <span className="text-faint"> – </span>
                    <span className="text-muted">{num(g.opponent_score)}</span>
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </Card>
  );
}

function ScoringTrendCard({ teamId }: { teamId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.teamScoringTrend(teamId),
    queryFn: () => fetchScoringTrend(teamId),
  });
  return (
    <Card>
      <CardHeader eyebrow="vs league average" title="Scoring Trend" />
      <div className="p-5">
        {isLoading && <Skeleton className="h-48 w-full" />}
        {data && data.points.length === 0 && <EmptyState title="No scores yet" />}
        {data && data.points.length > 0 && (
          <LineTrend
            title="Team score vs league average by week"
            data={data.points.map((p) => ({
              week: `Wk ${p.week}`,
              team: p.team_score ?? null,
              league: p.league_avg ?? null,
            }))}
            xKey="week"
            xLabel="Week"
            series={[
              { key: "team", label: "This team" },
              { key: "league", label: "League avg" },
            ]}
            height={240}
          />
        )}
      </div>
    </Card>
  );
}

/** One compact transaction line, shared by the exact log and the derived
 *  fallback so both read identically: a +/−/⇄ glyph, the player, faint detail,
 *  and the type pill. */
function TxRow({
  glyph,
  tone,
  primary,
  meta,
  label,
  title,
  faabBid,
}: {
  glyph: string;
  tone: "win" | "loss" | undefined;
  primary: string;
  meta: string;
  label: string;
  title?: string;
  faabBid?: number | null;
}) {
  const glyphColor = tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : "text-muted";
  return (
    <li className="flex items-center gap-2 px-5 py-2 text-[var(--fs-sm)]" title={title}>
      <span className={`num w-3 shrink-0 font-bold ${glyphColor}`}>{glyph}</span>
      <span className="shrink-0 text-text">{primary}</span>
      {meta && <span className="flex-1 truncate text-[var(--fs-xs)] text-faint">{meta}</span>}
      <span className="ml-auto flex shrink-0 items-center gap-1.5">
        {faabBid != null && (
          <span title={`Winning FAAB bid: $${faabBid}`}>
            <Pill tone="accent">${faabBid} FAAB</Pill>
          </span>
        )}
        <Pill tone={tone}>{label}</Pill>
      </span>
    </li>
  );
}

function weekLabel(week: number) {
  // Draft (and any pre-week-0 rows) bucket together as the season's opening.
  return week <= 0 ? "Draft" : `Week ${week}`;
}

type WeekGroup = { week: number; count: number; body: React.ReactNode };

/** Collapsible week sections for the transactions feed — newest week first, and
 *  the most recent week starts open so the latest moves are visible at a glance.
 *  Users expand/collapse at the week boundary. */
function WeekAccordion({ groups }: { groups: WeekGroup[] }) {
  const [open, setOpen] = useState<Set<number>>(
    () => new Set(groups.length ? [groups[0].week] : []),
  );
  const toggle = (w: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(w)) next.delete(w);
      else next.add(w);
      return next;
    });
  return (
    <div className="divide-y divide-[var(--hairline)]">
      {groups.map((g) => {
        const isOpen = open.has(g.week);
        return (
          <div key={g.week}>
            <button
              type="button"
              onClick={() => toggle(g.week)}
              aria-expanded={isOpen}
              className="flex w-full items-center justify-between gap-3 px-5 py-2 text-left hover:text-accent"
            >
              <span className="dz-eyebrow text-text">{weekLabel(g.week)}</span>
              <span className="flex items-center gap-2 text-[var(--fs-xs)] text-faint">
                {g.count}
                <span className="num text-muted">{isOpen ? "–" : "+"}</span>
              </span>
            </button>
            {isOpen && (
              <ol className="divide-y divide-[var(--hairline)] border-t border-[var(--hairline)] bg-[color:var(--surface-1)]">
                {g.body}
              </ol>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** A team's roster acquisitions: the exact recorded log when present, otherwise
 *  a single clearly-flagged fallback derived from week-to-week roster snapshots.
 *  Grouped into collapsible weeks (the draft is its own opening bucket). */
function TransactionsCard({ teamId }: { teamId: number }) {
  const tx = useQuery({
    queryKey: qk.teamTransactions(teamId),
    queryFn: () => fetchTransactions(teamId),
  });
  const exactRows = tx.data?.transactions ?? [];
  const hasExact = exactRows.length > 0;
  const exactEmpty = tx.data != null && !hasExact;

  // The derived diff is only fetched when the exact log is genuinely empty.
  const moves = useQuery({
    queryKey: qk.teamRosterMoves(teamId),
    queryFn: () => fetchRosterMoves(teamId),
    enabled: exactEmpty,
  });

  if (tx.isLoading) {
    return (
      <Card>
        <CardHeader eyebrow="recorded log" title="Transactions" />
        <Skeleton className="m-5 h-32" />
      </Card>
    );
  }

  // Preferred path: the exact recorded log, grouped by effective week.
  if (hasExact) {
    const byWeek = new Map<number, typeof exactRows>();
    for (const t of exactRows) {
      const w = t.effective_week ?? 0;
      const bucket = byWeek.get(w);
      if (bucket) bucket.push(t);
      else byWeek.set(w, [t]);
    }
    const groups: WeekGroup[] = [...byWeek.entries()]
      .sort((a, b) => b[0] - a[0])
      .map(([week, items]) => ({
        week,
        count: items.length,
        body: [...items]
          .sort((a, b) => (b.executed_at ?? "").localeCompare(a.executed_at ?? ""))
          .map((t) => (
            <TxRow
              key={t.transaction_id}
              glyph={txGlyph(t)}
              tone={transactionTone(t)}
              primary={transactionTitle(t)}
              meta={transactionDetail(t)}
              label={transactionLabel(t.transaction_type)}
              title={formatTransactionDateTime(t.executed_at)}
              faabBid={t.faab_bid}
            />
          )),
      }));
    return (
      <Card>
        <CardHeader
          eyebrow="recorded log"
          title="Transactions"
          action={<span className="text-[var(--fs-xs)] text-faint">{exactRows.length}</span>}
        />
        <WeekAccordion groups={groups} />
      </Card>
    );
  }

  // Fallback path: derive adds/drops from roster snapshots, flagged once and
  // grouped by the week the change first shows up.
  const md = moves.data;
  const churn = (md?.moves ?? []).filter((m) => m.action === "add" || m.action === "drop");
  const retained = md?.moves.filter((m) => m.action === "retain") ?? [];
  const byWeek = new Map<number, typeof churn>();
  for (const m of churn) {
    const bucket = byWeek.get(m.week);
    if (bucket) bucket.push(m);
    else byWeek.set(m.week, [m]);
  }
  const groups: WeekGroup[] = [...byWeek.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([week, items]) => ({
      week,
      count: items.length,
      body: items.map((m) => (
        <TxRow
          key={`${m.action}-${m.player_id}-${m.week}`}
          glyph={m.action === "add" ? "+" : "−"}
          tone={m.action === "add" ? "win" : "loss"}
          primary={m.player_name ?? "—"}
          meta={m.position ?? ""}
          label={m.action}
        />
      )),
    }));

  return (
    <Card>
      <CardHeader eyebrow="estimated from roster snapshots" title="Transactions" />
      <div className="px-5 pb-1 pt-3">
        <Badge variant="gap">
          Derived from week-to-week rosters — the exact transaction log wasn&apos;t available for
          this season.
        </Badge>
      </div>
      {moves.isLoading && <Skeleton className="m-5 h-32" />}
      {md && md.available === false && (
        <div className="p-5">
          <DataGap reason="roster_history_unavailable" size="sm" />
        </div>
      )}
      {md && md.available && churn.length === 0 && (
        <EmptyState title="No roster churn detected" hint="Roster snapshots show no adds or drops." />
      )}
      {md && md.available && churn.length > 0 && (
        <>
          <WeekAccordion groups={groups} />
          {retained.length > 0 && (
            <div className="border-t border-[var(--hairline)] px-5 py-3 text-[var(--fs-xs)] text-faint">
              {retained.length} player{retained.length === 1 ? "" : "s"} retained all season
            </div>
          )}
        </>
      )}
    </Card>
  );
}

const TX_LABELS: Record<string, string> = {
  free_agent_add: "Free agent",
  waiver_add: "Waiver",
  drop: "Drop",
  trade: "Trade",
  draft: "Draft",
};

function transactionLabel(type: string) {
  return TX_LABELS[type] ?? type.replaceAll("_", " ");
}

function txGlyph(t: TeamTransaction): string {
  if (t.transaction_type === "trade") return "⇄";
  if (t.transaction_type === "drop" || t.direction === "out") return "−";
  return "+";
}

function transactionTone(t: TeamTransaction): "win" | "loss" | undefined {
  if (t.transaction_type === "trade") return undefined;
  if (t.transaction_type === "drop" || t.direction === "out") return "loss";
  if (t.transaction_type.includes("add") || t.direction === "in") return "win";
  return undefined;
}

function transactionTitle(t: TeamTransaction) {
  return t.player_name ?? "Transaction";
}

// Detail line — the actor/device note is deliberately omitted (the team page
// already implies the owner made their own moves); keep only what's distinctive.
// The FAAB bid is promoted to its own pill (see TxRow), so it is not repeated here.
function transactionDetail(t: TeamTransaction) {
  const parts = [
    formatTransactionDate(t.executed_at),
    t.counterpart_team_name ? `with ${t.counterpart_team_name}` : null,
    t.waiver_priority_used != null ? `waiver #${t.waiver_priority_used}` : null,
  ].filter(Boolean);
  return parts.join(" · ");
}

function money(value: number) {
  return `$${Number.isInteger(value) ? value : value.toFixed(2)}`;
}

/** Weekly FAAB budget remaining, derived from tracked spend (NFL.com exposes no
 *  such view). Absent entirely for pre-FAAB (waiver-priority) seasons — that is
 *  not-applicable, not a gap, so the card simply doesn't render. */
function FaabBudgetCard({ teamId }: { teamId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.teamFaabBudget(teamId),
    queryFn: () => fetchFaabBudget(teamId),
  });

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (!data || !data.is_faab_era || !data.available) return null;

  const baseBudget = data.season_budget ?? 100;
  // The effective budget includes any mid-season credit (e.g. a +$37 refund), so
  // a refunded team doesn't read as overspent ("$137 of $137", not "of $100").
  const budget = data.weeks.length ? data.weeks[data.weeks.length - 1].budget : baseBudget;
  const adjusted = budget !== baseBudget;
  const remaining = data.final_remaining ?? budget;
  const spent = data.total_spent ?? 0;
  const overBudget = remaining < 0;
  const pct = Math.max(0, Math.min(100, (remaining / budget) * 100));

  return (
    <Card>
      <CardHeader
        eyebrow="FAAB budget"
        title="Waiver budget"
        action={
          overBudget ? (
            <span className="text-[var(--fs-sm)] font-semibold text-loss">over budget</span>
          ) : (
            <span className="num text-[var(--fs-sm)] text-text">
              {money(remaining)} <span className="text-faint">left</span>
            </span>
          )
        }
      />
      <div className="px-5 pb-3">
        <div className="text-[var(--fs-sm)] text-muted">
          Spent {money(spent)} of {money(budget)}
        </div>
        {adjusted && (
          <div className="text-[var(--fs-xs)] text-faint">
            Base {money(baseBudget)}, adjusted mid-season
          </div>
        )}
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--surface-2)]">
          <div
            className={`h-full rounded-full ${overBudget ? "bg-loss" : "bg-accent"}`}
            style={{ width: `${overBudget ? 100 : pct}%` }}
          />
        </div>
        {overBudget && (
          <div className="mt-2 text-[var(--fs-xs)] text-loss">
            Tracked spend exceeds the recorded budget for this team.
          </div>
        )}
      </div>
      <ol className="divide-y divide-[var(--hairline)] border-t border-[var(--hairline)]">
        {data.weeks.map((w) => (
          <li
            key={w.week}
            className="flex items-center gap-3 px-5 py-1.5 text-[var(--fs-sm)]"
          >
            <span className="dz-eyebrow w-12 shrink-0 text-faint">Wk {w.week}</span>
            <span className="num shrink-0 text-text">
              {w.spent > 0 ? `-${money(w.spent)}` : <span className="text-faint">—</span>}
            </span>
            {w.adjustment != null && w.note && <Pill tone="accent">{w.note}</Pill>}
            <span className="num ml-auto shrink-0 text-muted">
              {money(w.remaining)} <span className="text-faint">left</span>
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function formatTransactionDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatTransactionDateTime(value: string | null | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function TeamSeasonSelect({ ownerId, teamId }: { ownerId: number; teamId: number }) {
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: qk.ownerSeasons(ownerId),
    queryFn: () => fetchOwnerSeasons(ownerId),
  });
  const seasons = [...(data ?? [])]
    .filter((s) => s.team_id != null && s.season_year != null)
    .sort((a, b) => Number(b.season_year) - Number(a.season_year));

  if (seasons.length <= 1) return null;

  return (
    <label className="inline-flex items-center gap-2 text-[var(--fs-sm)] text-muted">
      Season
      <select
        className="dz-select py-1"
        aria-label="Team season"
        value={teamId}
        onChange={(e) => navigate(`/teams/${e.target.value}`)}
      >
        {seasons.map((s) => (
          <option key={s.team_id} value={s.team_id}>
            {s.season_year}
          </option>
        ))}
      </select>
    </label>
  );
}

export function TeamPage() {
  const params = useParams();
  const teamId = Number(params.teamId);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.team(teamId),
    queryFn: () => fetchOverview(teamId),
    enabled: Number.isFinite(teamId),
  });

  return (
    <div className="dz-rise space-y-4">
      <div>
        <div className="dz-eyebrow mb-1">
          {data ? `Season ${data.season_year}` : "Team"}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">
            {data?.team_name ?? "Team"}
          </h1>
          {data?.is_champion && <Trophy label="Champion" />}
          {data?.is_sacko && <Sacko />}
          {data && (
            <Link to={`/managers/${data.owner_id}`} className="text-muted hover:text-accent">
              {data.owner_name ?? "—"}
            </Link>
          )}
          {data && <TeamSeasonSelect ownerId={data.owner_id} teamId={teamId} />}
        </div>
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data && (
        <>
          <Card className="p-5">
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
              <Stat
                label="Rank"
                value={data.rank ?? "—"}
                unit={data.rank_basis === "final_rank" ? "official" : "computed"}
                tone="accent"
              />
              <div>
                <div className="dz-eyebrow mb-1">Record</div>
                <div className="font-display text-[30px] font-bold leading-none tracking-wide">
                  <RecordLine wins={data.wins} losses={data.losses} ties={data.ties} />
                </div>
              </div>
              <Stat label="Points for" value={num(data.points_for, 1)} tone="win" />
              <Stat label="Points against" value={num(data.points_against, 1)} tone="loss" />
            </div>
            {!data.is_scored && (
              <div className="mt-4 border-t border-[var(--hairline)] pt-4">
                <Badge variant="gap">{UNSCORED_SEASON_NOTE}</Badge>
              </div>
            )}
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RosterCard teamId={teamId} />
            <ScheduleCard teamId={teamId} boxScoresAvailable={data.is_scored} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ScoringTrendCard teamId={teamId} />
            <TransactionsCard teamId={teamId} />
          </div>

          {/* FAAB budget — renders only for FAAB-era seasons (self-hiding). */}
          <FaabBudgetCard teamId={teamId} />
        </>
      )}
    </div>
  );
}
