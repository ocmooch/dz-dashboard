import { Fragment } from "react";
import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, DataGap, RecordLine } from "@/design-system";
import { num } from "@/lib/format";

// The bundle is intentionally loose on the wire — each band carries its own rich,
// deep-linkable context (matchup_id, heat components, owner refs). The generated
// client only guarantees the envelope, so we widen here exactly like PairwisePage.
type OwnerRef = {
  owner_id: number;
  display_name?: string | null;
  // Enriched by the BFF so bands can dim/order departed managers in place.
  is_active?: boolean;
  prominence?: number;
};
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
  most_played?: PairRecord[];
  dead_even?: PairRecord[];
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
  from_matchup_id?: number | null;
  last_matchup_id?: number | null;
};
type NemesisRow = {
  owner: OwnerRef;
  nemesis: OppRecord | null;
  favorite_victim: OppRecord | null;
  nemesis_departed?: OppRecord | null;
  favorite_victim_departed?: OppRecord | null;
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

// A pairing is "departed" (deprioritized in place) if either side has left the
// league — the BFF has already ranked these below the active ones; the UI only
// has to dim them so active-manager rivalries read as the headline.
const isDeparted = (o?: OwnerRef) => o?.is_active === false;
const pairDeparted = (a: OwnerRef, b: OwnerRef) => isDeparted(a) || isDeparted(b);

// A faint "former" chip, used wherever a departed manager appears in a ranking so
// the deprioritization is legible rather than mysterious.
function FormerTag() {
  return <span className="dz-pill ml-2 text-[var(--fs-xs)] text-faint">former</span>;
}

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

// A divider that drops in once, ahead of the first departed entry in a ranked
// list, so the active block reads first and the rest is clearly "history".
function FormerDivider() {
  return (
    <li aria-hidden className="dz-eyebrow flex items-center gap-2 pt-1 text-faint">
      <span className="h-px flex-1 bg-[var(--hairline)]" />
      former managers
      <span className="h-px flex-1 bg-[var(--hairline)]" />
    </li>
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
            {band.leaderboard.map((r, i) => {
              const departed = pairDeparted(r.owner_a, r.owner_b);
              const prev = band.leaderboard![i - 1];
              const firstDeparted =
                departed && (i === 0 || !pairDeparted(prev.owner_a, prev.owner_b));
              return (
                <Fragment key={`${r.owner_a.owner_id}-${r.owner_b.owner_id}`}>
                  {firstDeparted && <FormerDivider />}
                  <li className={`flex items-center gap-4 ${departed ? "opacity-60" : ""}`}>
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
                </Fragment>
              );
            })}
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

// A numbered list of pairings, dimmed + divided once the ranking crosses into
// former managers. ``kind`` only changes the trailing stat line.
function PairRankList({
  label,
  rows,
  kind,
}: {
  label: string;
  rows?: PairRecord[];
  kind: "played" | "even";
}) {
  return (
    <div className="bg-[var(--surface-1)] p-5">
      <div className="dz-eyebrow mb-3">{label}</div>
      {!rows || rows.length === 0 ? (
        <DataGap reason="no_meetings" size="sm" />
      ) : (
        <ol className="space-y-2">
          {rows.map((p, i) => {
            const departed = pairDeparted(p.owner_a, p.owner_b);
            const prev = rows[i - 1];
            const firstDeparted =
              departed && (i === 0 || !pairDeparted(prev.owner_a, prev.owner_b));
            return (
              <Fragment key={`${p.owner_a.owner_id}-${p.owner_b.owner_id}`}>
                {firstDeparted && <FormerDivider />}
                <li
                  className={`flex items-baseline justify-between gap-3 ${departed ? "opacity-60" : ""}`}
                >
                  <span className="min-w-0 truncate">
                    <span className="num mr-2 text-faint">{i + 1}</span>
                    <Link
                      to={pairTo(p.owner_a, p.owner_b)}
                      className="font-semibold hover:text-accent"
                    >
                      {name(p.owner_a)} <span className="text-faint">vs</span> {name(p.owner_b)}
                    </Link>
                  </span>
                  <span className="num shrink-0 text-[var(--fs-sm)] text-muted">
                    {kind === "played" ? (
                      <>
                        {p.games}g ·{" "}
                        <RecordLine wins={p.a_wins} losses={p.b_wins} ties={p.ties} />
                      </>
                    ) : (
                      <>
                        {p.a_wins}–{p.b_wins}
                        {p.ties ? `–${p.ties}` : ""} · {p.games}g
                      </>
                    )}
                  </span>
                </li>
              </Fragment>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function RecordsBand({ band }: { band: RivalryInsightsData["records"] }) {
  return (
    <Card>
      <CardHeader eyebrow="the record book" title="Rivalry Superlatives" />
      {/* Absolute single-game records — pure all-time, never deprioritized. */}
      <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-3">
        <MeetingRecord label="Closest game ever" m={band.closest_game} />
        <MeetingRecord label="Biggest beating" m={band.biggest_blowout} />
        <MeetingRecord label="Highest-scoring duel" m={band.highest_scoring_duel} />
      </div>
      {/* Ranked pairings — active first, former managers dimmed below. */}
      <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2">
        <PairRankList label="Most-played rivalries" rows={band.most_played} kind="played" />
        <PairRankList label="Most dead-even rivalries" rows={band.dead_even} kind="even" />
      </div>
    </Card>
  );
}

// The span of a (possibly cross-season) streak, with both ends deep-linked to
// their matchups so the run is browsable start → end, not just at the last game.
function StreakSpan({ streak }: { streak: Streak }) {
  return (
    <span className="text-[var(--fs-xs)]">
      <MatchupLink matchupId={streak.from_matchup_id}>
        <When year={streak.from_year} />
      </MatchupLink>{" "}
      <span className="text-faint">→</span>{" "}
      <MatchupLink matchupId={streak.last_matchup_id}>
        <When year={streak.to_year} />
      </MatchupLink>
    </span>
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
            <div>
              <span className="font-display text-[26px] font-bold text-accent">
                {band.longest.length}
              </span>{" "}
              <Link
                to={pairTo(band.longest.owner, band.longest.opponent)}
                className="font-semibold text-text hover:text-accent"
              >
                — {name(band.longest.owner)} over {name(band.longest.opponent)}
              </Link>
            </div>
            <div className="mt-1 text-[var(--fs-sm)] text-muted">
              also {name(band.longest.opponent)}&apos;s longest losing skid to one rival ·{" "}
              <StreakSpan streak={band.longest} />
            </div>
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
                    className={`dz-pill hover:text-accent ${isDeparted(s.owner) ? "opacity-60" : ""}`}
                    title={`${name(s.owner)} has won the last ${s.length} vs ${name(s.opponent)} — ${name(s.opponent)} has dropped ${s.length} straight`}
                  >
                    <span className="font-semibold">{name(s.owner)}</span>
                    <span className="text-faint"> W{s.length} </span>
                    <span className="text-muted">vs {name(s.opponent)}</span>
                    {isDeparted(s.owner) && <FormerTag />}
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

// One nemesis/victim cell: the headline opponent (chosen among current/long-stint
// managers) plus, when it exists, a dimmed "vs former …" line for an even more
// extreme record against a short-stint departed opponent — kept visible, never
// the headline.
function OppCell({
  owner,
  primary,
  departed,
  tone,
}: {
  owner: OwnerRef;
  primary: OppRecord | null;
  departed?: OppRecord | null;
  tone: "win" | "loss";
}) {
  const toneClass = tone === "win" ? "text-win" : "text-loss";
  return (
    <div className="bg-[var(--surface-1)] px-4 py-3">
      {primary ? (
        <Link to={pairTo(owner, primary.opponent)} className="block hover:text-accent">
          <span className={`font-semibold ${toneClass}`}>{name(primary.opponent)}</span>
          <span className="num ml-2 text-[var(--fs-xs)] text-muted">
            {primary.wins}–{primary.losses}
            {primary.ties ? `–${primary.ties}` : ""}
          </span>
        </Link>
      ) : (
        <DataGap reason="insufficient_rivalry_history" size="sm" />
      )}
      {departed && (
        <Link
          to={pairTo(owner, departed.opponent)}
          className="mt-1 block opacity-60 hover:text-accent"
        >
          <span className="text-[var(--fs-xs)] text-faint">vs former </span>
          <span className={`text-[var(--fs-xs)] font-semibold ${toneClass}`}>
            {name(departed.opponent)}
          </span>
          <span className="num ml-1 text-[var(--fs-xs)] text-faint">
            {departed.wins}–{departed.losses}
            {departed.ties ? `–${departed.ties}` : ""}
          </span>
        </Link>
      )}
    </div>
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
      <OppCell owner={row.owner} primary={row.nemesis} departed={row.nemesis_departed} tone="loss" />
      <OppCell
        owner={row.owner}
        primary={row.favorite_victim}
        departed={row.favorite_victim_departed}
        tone="win"
      />
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
