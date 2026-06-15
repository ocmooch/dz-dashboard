import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, DataGap, RecordLine } from "@/design-system";
import { num } from "@/lib/format";

// The bundle is intentionally loose on the wire — each band carries its own rich,
// deep-linkable context (matchup_id, heat components, owner refs). The generated
// client only guarantees the envelope, so we widen here exactly like PairwisePage.
type OwnerRef = { owner_id: number; display_name?: string | null };
type Band = { available?: boolean; reason?: string | null };

type RecordMeeting = {
  winner: OwnerRef;
  loser: OwnerRef;
  winner_score: number;
  loser_score: number;
  margin: number;
  combined: number;
  season_year?: number | null;
  week?: number | null;
  matchup_id?: number | null;
  is_playoff?: boolean;
};
type PairRecord = {
  owner_a: OwnerRef;
  owner_b: OwnerRef;
  games: number;
  a_wins: number;
  b_wins: number;
  ties: number;
};
type Records = Band & {
  closest_game?: RecordMeeting;
  biggest_blowout?: RecordMeeting;
  highest_scoring_duel?: RecordMeeting;
  most_played_pairing?: PairRecord;
  dead_even_rivalry?: {
    owner_a: OwnerRef;
    owner_b: OwnerRef;
    games_played: number;
    a_wins: number;
    b_wins: number;
  } | null;
};
type IntensityRow = {
  owner_a: OwnerRef;
  owner_b: OwnerRef;
  heat: number;
  games: number;
  a_wins: number;
  b_wins: number;
  ties: number;
  playoff_meetings: number;
  last_meeting: { season_year?: number | null; week?: number | null; matchup_id?: number | null };
};
type Streak = {
  owner: OwnerRef;
  opponent: OwnerRef;
  length: number;
  from_year?: number | null;
  to_year?: number | null;
  last_matchup_id?: number | null;
};
type NemesisRow = {
  owner: OwnerRef;
  nemesis: OppRecord | null;
  favorite_victim: OppRecord | null;
};
type OppRecord = {
  opponent: OwnerRef;
  games: number;
  wins: number;
  losses: number;
  ties: number;
  win_pct: number;
};
type PlayoffRow = {
  owner_a: OwnerRef;
  owner_b: OwnerRef;
  playoff_meetings: number;
  a_wins: number;
  b_wins: number;
  ties: number;
  last_meeting: { season_year?: number | null; week?: number | null; matchup_id?: number | null };
  finals_meeting?: { season_year?: number | null; label?: string | null; matchup_id?: number | null } | null;
};

export type RivalryInsightsData = {
  records: Records;
  streaks: Band & { longest?: Streak; active?: Streak[] };
  intensity: Band & { leaderboard?: IntensityRow[] };
  nemeses: Band & { managers?: NemesisRow[] };
  playoffs: Band & { rivalries?: PlayoffRow[] };
};

const name = (o: OwnerRef | undefined) => o?.display_name ?? (o ? `#${o.owner_id}` : "—");
const pairTo = (a: OwnerRef, b: OwnerRef) => `/rivalries/${a.owner_id}/vs/${b.owner_id}`;

function When({ year, week }: { year?: number | null; week?: number | null }) {
  if (!year) return <span className="text-faint">—</span>;
  return (
    <span className="text-[var(--fs-xs)] text-faint">
      {year}
      {week != null && ` · wk ${week}`}
    </span>
  );
}

// A clickable pairing — the connective tissue of every band. Routes to the full
// pairwise page so any insight is one tap from its receipts.
function PairLink({ a, b, className = "" }: { a: OwnerRef; b: OwnerRef; className?: string }) {
  return (
    <Link to={pairTo(a, b)} className={`font-semibold hover:text-accent ${className}`.trim()}>
      {name(a)} <span className="text-faint">vs</span> {name(b)}
    </Link>
  );
}

function MatchupLink({
  matchupId,
  children,
}: {
  matchupId?: number | null;
  children: React.ReactNode;
}) {
  if (matchupId == null) return <>{children}</>;
  return (
    <Link to={`/matchups/${matchupId}`} className="hover:text-accent">
      {children}
    </Link>
  );
}

// ── Band 1 · the centerpiece ──────────────────────────────────────────────
function IntensityBand({ band }: { band: RivalryInsightsData["intensity"] }) {
  return (
    <Card>
      <CardHeader
        eyebrow="who it's hottest between"
        title="Hottest Rivalries"
        action={<Badge variant="accent">heat index</Badge>}
      />
      <div className="p-5">
        {!band.available || !band.leaderboard?.length ? (
          <DataGap reason={band.reason ?? "insufficient_rivalry_history"} />
        ) : (
          <ol className="space-y-3">
            {band.leaderboard.map((r, i) => (
              <li key={`${r.owner_a.owner_id}-${r.owner_b.owner_id}`} className="flex items-center gap-4">
                <span className="font-display text-[22px] font-bold text-faint w-6 tabular-nums">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <PairLink a={r.owner_a} b={r.owner_b} />
                    <span className="num text-[var(--fs-sm)] text-muted">
                      {r.a_wins}–{r.b_wins}
                      {r.ties ? `–${r.ties}` : ""} · {r.games}g
                      {r.playoff_meetings > 0 && ` · ${r.playoff_meetings} playoff`}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full rounded bg-[var(--hairline)]">
                    <div
                      className="h-full rounded bg-accent"
                      style={{ width: `${Math.max(2, Math.min(100, r.heat))}%` }}
                    />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-4 text-[var(--fs-xs)] text-faint">
          Heat blends how even the series is, how close the games run, how recently they met,
          how often, and how much was at stake. Ties to the records book — never a black box.
        </p>
      </div>
    </Card>
  );
}

// ── Band 2 · league-wide superlatives ─────────────────────────────────────
function MeetingRecord({ label, m }: { label: string; m?: RecordMeeting }) {
  return (
    <div className="bg-[var(--surface-1)] p-5">
      <div className="dz-eyebrow mb-2">{label}</div>
      {m ? (
        <MatchupLink matchupId={m.matchup_id}>
          <div className="font-semibold text-text">
            {name(m.winner)} <span className="text-faint">def.</span> {name(m.loser)}
          </div>
          <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
            {num(m.winner_score)} – {num(m.loser_score)}
            <span className="text-faint"> · </span>
            {label.startsWith("Highest") ? `${num(m.combined)} combined` : `by ${num(m.margin)}`}
          </div>
          <When year={m.season_year} week={m.week} />
        </MatchupLink>
      ) : (
        <DataGap reason="no_meetings" size="sm" />
      )}
    </div>
  );
}

function RecordsBand({ band }: { band: RivalryInsightsData["records"] }) {
  const most = band.most_played_pairing;
  const even = band.dead_even_rivalry;
  return (
    <Card>
      <CardHeader eyebrow="the record book" title="Rivalry Superlatives" />
      <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-3">
        <MeetingRecord label="Closest game ever" m={band.closest_game} />
        <MeetingRecord label="Biggest beating" m={band.biggest_blowout} />
        <MeetingRecord label="Highest-scoring duel" m={band.highest_scoring_duel} />
        <div className="bg-[var(--surface-1)] p-5">
          <div className="dz-eyebrow mb-2">Most-played pairing</div>
          {most ? (
            <Link to={pairTo(most.owner_a, most.owner_b)} className="block hover:text-accent">
              <div className="font-semibold text-text">
                {name(most.owner_a)} <span className="text-faint">vs</span> {name(most.owner_b)}
              </div>
              <div className="mt-0.5 text-[var(--fs-sm)] text-muted">
                {most.games} meetings · <RecordLine wins={most.a_wins} losses={most.b_wins} ties={most.ties} />
              </div>
            </Link>
          ) : (
            <DataGap reason="no_meetings" size="sm" />
          )}
        </div>
        <div className="bg-[var(--surface-1)] p-5">
          <div className="dz-eyebrow mb-2">Most dead-even</div>
          {even ? (
            <Link to={pairTo(even.owner_a, even.owner_b)} className="block hover:text-accent">
              <div className="font-semibold text-text">
                {name(even.owner_a)} <span className="text-faint">vs</span> {name(even.owner_b)}
              </div>
              <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
                {even.a_wins}–{even.b_wins} over {even.games_played} games
              </div>
            </Link>
          ) : (
            <DataGap reason="no_meetings" size="sm" />
          )}
        </div>
      </div>
    </Card>
  );
}

// ── Band 3 · streaks ──────────────────────────────────────────────────────
function StreaksBand({ band }: { band: RivalryInsightsData["streaks"] }) {
  const active = (band.active ?? []).slice(0, 8);
  return (
    <Card>
      <CardHeader eyebrow="domination" title="Win Streaks" />
      <div className="p-5 space-y-4">
        {band.longest ? (
          <div>
            <div className="dz-eyebrow mb-1">Longest ever</div>
            <Link to={pairTo(band.longest.owner, band.longest.opponent)} className="hover:text-accent">
              <span className="font-display text-[26px] font-bold text-accent">{band.longest.length}</span>{" "}
              <span className="font-semibold text-text">
                — {name(band.longest.owner)} over {name(band.longest.opponent)}
              </span>{" "}
              <When year={band.longest.from_year} /> <span className="text-faint">→</span>{" "}
              <When year={band.longest.to_year} />
            </Link>
          </div>
        ) : (
          <DataGap reason="no_meetings" />
        )}
        {active.length > 0 && (
          <div className="border-t border-[var(--hairline)] pt-4">
            <div className="dz-eyebrow mb-2">Currently riding</div>
            <ul className="flex flex-wrap gap-2">
              {active.map((s) => (
                <li key={`${s.owner.owner_id}-${s.opponent.owner_id}`}>
                  <Link
                    to={pairTo(s.owner, s.opponent)}
                    className="dz-pill hover:text-accent"
                    title={`${name(s.owner)} has won the last ${s.length} vs ${name(s.opponent)}`}
                  >
                    <span className="font-semibold">{name(s.owner)}</span>
                    <span className="text-faint"> W{s.length} </span>
                    <span className="text-muted">vs {name(s.opponent)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}

// ── Band 4 · the "check your own row" magnet ──────────────────────────────
function NemesesBand({ band }: { band: RivalryInsightsData["nemeses"] }) {
  const rows = band.managers ?? [];
  return (
    <Card>
      <CardHeader eyebrow="every active manager" title="Nemesis & Favorite Victim" />
      <div className="p-5">
        {rows.length === 0 ? (
          <DataGap reason="insufficient_rivalry_history" />
        ) : (
          <div className="overflow-hidden rounded border border-[var(--hairline)]">
            <div className="grid grid-cols-[1.2fr_1fr_1fr] gap-px bg-[var(--border)] text-[var(--fs-xs)]">
              <div className="dz-eyebrow bg-[var(--surface-1)] px-4 py-2">Manager</div>
              <div className="dz-eyebrow bg-[var(--surface-1)] px-4 py-2">Nemesis</div>
              <div className="dz-eyebrow bg-[var(--surface-1)] px-4 py-2">Favorite victim</div>
              {rows.map((r) => (
                <RowGroup key={r.owner.owner_id} row={r} />
              ))}
            </div>
          </div>
        )}
        <p className="mt-3 text-[var(--fs-xs)] text-faint">
          Worst and best all-time records against any one manager (minimum shared games). A
          quiet gap means no rivalry has crossed that bar yet — never a fake 0–0.
        </p>
      </div>
    </Card>
  );
}

function RowGroup({ row }: { row: NemesisRow }) {
  return (
    <>
      <div className="bg-[var(--surface-1)] px-4 py-3">
        <Link to={`/managers/${row.owner.owner_id}`} className="font-semibold text-text hover:text-accent">
          {name(row.owner)}
        </Link>
      </div>
      <div className="bg-[var(--surface-1)] px-4 py-3">
        {row.nemesis ? (
          <Link to={pairTo(row.owner, row.nemesis.opponent)} className="block hover:text-accent">
            <span className="font-semibold text-loss">{name(row.nemesis.opponent)}</span>
            <span className="num ml-2 text-[var(--fs-xs)] text-muted">
              {row.nemesis.wins}–{row.nemesis.losses}
              {row.nemesis.ties ? `–${row.nemesis.ties}` : ""}
            </span>
          </Link>
        ) : (
          <DataGap reason="insufficient_rivalry_history" size="sm" />
        )}
      </div>
      <div className="bg-[var(--surface-1)] px-4 py-3">
        {row.favorite_victim ? (
          <Link to={pairTo(row.owner, row.favorite_victim.opponent)} className="block hover:text-accent">
            <span className="font-semibold text-win">{name(row.favorite_victim.opponent)}</span>
            <span className="num ml-2 text-[var(--fs-xs)] text-muted">
              {row.favorite_victim.wins}–{row.favorite_victim.losses}
              {row.favorite_victim.ties ? `–${row.favorite_victim.ties}` : ""}
            </span>
          </Link>
        ) : (
          <DataGap reason="insufficient_rivalry_history" size="sm" />
        )}
      </div>
    </>
  );
}

// ── Band 5 · postseason stakes ────────────────────────────────────────────
function PlayoffBand({ band }: { band: RivalryInsightsData["playoffs"] }) {
  const rows = band.rivalries ?? [];
  return (
    <Card>
      <CardHeader eyebrow="when it counted" title="Playoff Rivalries" />
      <div className="p-5">
        {!band.available || rows.length === 0 ? (
          <DataGap reason={band.reason ?? "no_playoff_meetings"} />
        ) : (
          <ul className="space-y-3">
            {rows.map((r) => (
              <li
                key={`${r.owner_a.owner_id}-${r.owner_b.owner_id}`}
                className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[var(--hairline)] pb-3 last:border-0 last:pb-0"
              >
                <div>
                  <PairLink a={r.owner_a} b={r.owner_b} />
                  <span className="num ml-2 text-[var(--fs-sm)] text-muted">
                    {r.a_wins}–{r.b_wins}
                    {r.ties ? `–${r.ties}` : ""} in {r.playoff_meetings} postseason
                    {r.playoff_meetings === 1 ? " meeting" : " meetings"}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  {r.finals_meeting?.label && (
                    <Badge variant="accent">
                      {r.finals_meeting.season_year} {r.finals_meeting.label}
                    </Badge>
                  )}
                  <MatchupLink matchupId={r.last_meeting.matchup_id}>
                    <When year={r.last_meeting.season_year} week={r.last_meeting.week} />
                  </MatchupLink>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

export function RivalryInsights({ data }: { data: RivalryInsightsData }) {
  return (
    <>
      <IntensityBand band={data.intensity} />
      <RecordsBand band={data.records} />
      <StreaksBand band={data.streaks} />
      <NemesesBand band={data.nemeses} />
      <PlayoffBand band={data.playoffs} />
    </>
  );
}
