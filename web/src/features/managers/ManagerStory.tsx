import { Link } from "react-router-dom";

import { Badge, Card, CardHeader } from "@/design-system";
import { num } from "@/lib/format";

// The /story bundle is intentionally loose on the wire: each superlative is its
// own rich, deep-linkable object or null when it doesn't clear its bar. The
// generated client only guarantees the envelope, so we widen here exactly like
// RivalryInsights does for its bands.
type OwnerRef = { owner_id: number; display_name?: string | null };
type Meeting = {
  opponent: OwnerRef;
  owner_score: number;
  opponent_score: number;
  margin: number;
  season_year?: number | null;
  week?: number | null;
  matchup_id?: number | null;
  is_playoff?: boolean;
};
type HighWater = {
  opponent: OwnerRef;
  score: number;
  opponent_score: number;
  season_year?: number | null;
  week?: number | null;
  matchup_id?: number | null;
};
type OppRecord = {
  opponent: OwnerRef;
  games: number;
  wins: number;
  losses: number;
  ties: number;
  win_pct: number;
};
type LuckSeason = {
  season_year?: number | null;
  luck_delta: number;
  actual_wins: number;
  expected_wins: number;
};

export type OwnerStoryData = {
  owner: OwnerRef;
  available: boolean;
  signature_win?: Meeting | null;
  heartbreak?: Meeting | null;
  high_water_mark?: HighWater | null;
  nemesis?: OppRecord | null;
  favorite_victim?: OppRecord | null;
  luckiest_season?: LuckSeason | null;
  unluckiest_season?: LuckSeason | null;
};

const name = (o: OwnerRef | undefined) => o?.display_name ?? (o ? `#${o.owner_id}` : "—");

function When({ year, week }: { year?: number | null; week?: number | null }) {
  if (!year) return null;
  return (
    <span className="text-[var(--fs-xs)] text-faint">
      {year}
      {week != null && ` · wk ${week}`}
    </span>
  );
}

/** A single voiced superlative tile. Routes to its receipt — a box score for a
 *  game, the pairwise page for a rivalry — so the claim is one tap from proof. */
function Tile({
  eyebrow,
  to,
  tone,
  children,
}: {
  eyebrow: string;
  to?: string;
  tone?: "win" | "loss";
  children: React.ReactNode;
}) {
  const accent = tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : "text-text";
  const body = (
    <>
      <div className="dz-eyebrow mb-2">{eyebrow}</div>
      <div className={`font-semibold ${accent}`}>{children}</div>
    </>
  );
  return (
    <div className="bg-[var(--surface-1)] p-5">
      {to ? (
        <Link to={to} className="block hover:text-accent">
          {body}
        </Link>
      ) : (
        body
      )}
    </div>
  );
}

/** The "Your Story" lead band — a personal highlight reel of voiced superlatives.
 *  Each tile renders only when its data cleared its bar; a gated-out line is simply
 *  absent (never a forced 0 or fake value). When nothing clears, the band hides. */
export function ManagerStory({ story }: { story: OwnerStoryData }) {
  if (!story.available) return null;
  const oid = story.owner.owner_id;
  const matchup = (id?: number | null) => (id != null ? `/matchups/${id}` : undefined);
  const pair = (b: OwnerRef) => `/rivalries/${oid}/vs/${b.owner_id}`;

  const sig = story.signature_win;
  const hb = story.heartbreak;
  const hw = story.high_water_mark;
  const nem = story.nemesis;
  const vic = story.favorite_victim;
  const lucky = story.luckiest_season;
  const robbed = story.unluckiest_season;

  return (
    <Card>
      <CardHeader
        eyebrow="the highlight reel"
        title="Your Story"
        action={<Badge variant="accent">superlatives</Badge>}
      />
      <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-3">
        {sig && (
          <Tile eyebrow="Signature win" to={matchup(sig.matchup_id)} tone="win">
            A <span className="num">{num(sig.margin)}</span>-point beating of {name(sig.opponent)}
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              {num(sig.owner_score)} – {num(sig.opponent_score)} · <When year={sig.season_year} week={sig.week} />
            </div>
          </Tile>
        )}
        {hb && (
          <Tile eyebrow={hb.is_playoff ? "Playoff heartbreak" : "Heartbreak"} to={matchup(hb.matchup_id)} tone="loss">
            {hb.is_playoff ? "Knocked out by " : "Lost to "}
            {name(hb.opponent)} by <span className="num">{num(hb.margin)}</span>
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              {num(hb.owner_score)} – {num(hb.opponent_score)} · <When year={hb.season_year} week={hb.week} />
            </div>
          </Tile>
        )}
        {hw && (
          <Tile eyebrow="High-water mark" to={matchup(hw.matchup_id)}>
            <span className="num text-accent">{num(hw.score)}</span> — their highest score ever
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              vs {name(hw.opponent)} · <When year={hw.season_year} week={hw.week} />
            </div>
          </Tile>
        )}
        {nem && (
          <Tile eyebrow="Kryptonite" to={pair(nem.opponent)} tone="loss">
            {name(nem.opponent)} owns them
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              {nem.wins}–{nem.losses}
              {nem.ties ? `–${nem.ties}` : ""} over {nem.games} games
            </div>
          </Tile>
        )}
        {vic && (
          <Tile eyebrow="Favorite victim" to={pair(vic.opponent)} tone="win">
            They own {name(vic.opponent)}
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              {vic.wins}–{vic.losses}
              {vic.ties ? `–${vic.ties}` : ""} over {vic.games} games
            </div>
          </Tile>
        )}
        {lucky && (
          <Tile eyebrow="Luckiest season">
            {lucky.season_year} — the schedule gave them{" "}
            <span className="num text-win">{num(lucky.luck_delta)}</span> wins
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              {num(lucky.actual_wins)} actual vs {num(lucky.expected_wins)} expected
            </div>
          </Tile>
        )}
        {robbed && (
          <Tile eyebrow="Robbed">
            {robbed.season_year} — the schedule cost them{" "}
            <span className="num text-loss">{num(Math.abs(robbed.luck_delta))}</span> wins
            <div className="num mt-0.5 text-[var(--fs-sm)] text-muted">
              {num(robbed.actual_wins)} actual vs {num(robbed.expected_wins)} expected
            </div>
          </Tile>
        )}
      </div>
    </Card>
  );
}
