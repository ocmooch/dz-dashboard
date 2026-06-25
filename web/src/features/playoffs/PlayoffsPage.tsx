import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Card, CardHeader, Chip, DataGap, ErrorState, Skeleton } from "@/design-system";
import { PowerTable } from "@/features/power/PowerTable";
import { usePower } from "@/features/power/usePower";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { num, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type BracketSection = components["schemas"]["BracketSection"];
type BracketRound = components["schemas"]["BracketRound"];
type BracketGame = components["schemas"]["BracketGame"];
type ByeTeam = components["schemas"]["ByeTeam"];

async function fetchBracket(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/bracket", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load bracket");
  return data.data;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

// Sort key for finals-round games: Championship → 1st, then ascending by place number.
function gameRank(label: string | null | undefined): number {
  if (!label) return 99;
  if (label === "Championship") return 0;
  const m = label.match(/^(\d+)/);
  return m ? parseInt(m[1], 10) : 99;
}

// ── Team row ──────────────────────────────────────────────────────────────────

function TeamRow({
  team,
  byeTeamIds,
}: {
  team: NonNullable<BracketGame["team_a"]>;
  byeTeamIds: Set<number>;
}) {
  const hadBye = byeTeamIds.has(team.team_id);
  return (
    <div
      className={`flex items-center justify-between gap-2 rounded-[var(--radius-sm)] px-2.5 py-1.5 ${
        team.is_winner ? "bg-[var(--surface-1)]" : "bg-transparent"
      }`}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <div className="min-w-0 flex-1 overflow-hidden">
          <Chip
            name={team.team_name ?? team.owner_name ?? "—"}
            sub={team.team_name ? (team.owner_name ?? undefined) : undefined}
            avatarUrl={teamAvatarUrl(team.team_id)}
          />
        </div>
        {team.is_sacko && (
          <span className="shrink-0 text-[var(--fs-sm)]" title="Sacko — toilet-bowl loser" aria-label="Sacko">
            💩
          </span>
        )}
        {hadBye && (
          <span className="shrink-0 rounded border border-[var(--border)] px-1 py-px text-[9px] font-semibold uppercase tracking-widest text-faint">
            Bye
          </span>
        )}
      </div>
      <span
        className={`num shrink-0 tabular-nums text-[var(--fs-sm)] ${
          team.is_winner ? "font-semibold text-win" : "text-muted"
        }`}
      >
        {team.score != null ? num(team.score) : "—"}
      </span>
    </div>
  );
}

// ── Game card ─────────────────────────────────────────────────────────────────

function GameCard({
  game,
  variant = "regular",
  byeTeamIds,
}: {
  game: BracketGame;
  variant?: "championship" | "regular" | "secondary";
  byeTeamIds: Set<number>;
}) {
  const isChamp = variant === "championship";
  return (
    <Link
      to={`/matchups/${game.matchup_id}`}
      className={[
        "block rounded-[var(--radius)] border bg-[var(--surface-0)] transition-colors hover:border-[var(--accent)]",
        isChamp
          ? "border-[var(--accent)] p-3.5 shadow-sm"
          : "border-[var(--border)] p-3",
        variant === "secondary" ? "opacity-70" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {game.game_label && (
        <div className="mb-2">
          <span
            className={`text-[10px] font-semibold uppercase tracking-widest ${
              isChamp ? "text-[var(--accent)]" : "text-muted"
            }`}
          >
            {game.game_label}
          </span>
        </div>
      )}
      <div className="space-y-0.5">
        {game.team_a && <TeamRow team={game.team_a} byeTeamIds={byeTeamIds} />}
        {game.team_b && <TeamRow team={game.team_b} byeTeamIds={byeTeamIds} />}
      </div>
    </Link>
  );
}

// ── Bye slot (first-round bye display) ───────────────────────────────────────

function ByeSlot({ team }: { team: ByeTeam }) {
  return (
    <div className="flex items-center justify-between rounded-[var(--radius)] border border-dashed border-[var(--border)] px-3 py-2 opacity-50">
      <Chip
        name={team.team_name ?? team.owner_name ?? "—"}
        sub={team.team_name ? (team.owner_name ?? undefined) : undefined}
        avatarUrl={teamAvatarUrl(team.team_id)}
      />
      <span className="text-[10px] font-semibold uppercase tracking-widest text-faint">
        Bye
      </span>
    </div>
  );
}

// ── Round column ──────────────────────────────────────────────────────────────

function RoundColumn({
  round,
  isFirst,
  isLast,
  byeTeamIds,
}: {
  round: BracketRound;
  isFirst: boolean;
  isLast: boolean;
  byeTeamIds: Set<number>;
}) {
  let mainGames = round.games;
  let secondaryGames: BracketGame[] = [];

  if (isLast && round.games.length > 1) {
    const sorted = [...round.games].sort(
      (a, b) => gameRank(a.game_label) - gameRank(b.game_label)
    );
    mainGames = [sorted[0]];
    secondaryGames = sorted.slice(1);
  }

  const champVariant = isLast && mainGames.length === 1 ? "championship" : "regular";

  return (
    <div
      className={`flex flex-col gap-2.5 ${
        !isLast ? "border-r border-[var(--hairline)]" : ""
      }`}
    >
      {/* Round label */}
      <div className="pb-1 text-[11px] font-semibold uppercase tracking-widest text-muted">
        {round.round_label}
      </div>

      {/* Primary games */}
      {mainGames.map((game) => (
        <GameCard
          key={game.matchup_id}
          game={game}
          variant={champVariant}
          byeTeamIds={byeTeamIds}
        />
      ))}

      {/* First-round bye slots (shown only in round 1) */}
      {isFirst && round.bye_teams.length > 0 && (
        <div className="mt-1 flex flex-col gap-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-faint">
            First Round Bye
          </div>
          {round.bye_teams.map((team) => (
            <ByeSlot key={team.team_id} team={team} />
          ))}
        </div>
      )}

      {/* Secondary finals games (3rd/5th place, etc.) */}
      {secondaryGames.length > 0 && (
        <div className="mt-1 flex flex-col gap-2 border-t border-[var(--hairline)] pt-3">
          {secondaryGames.map((game) => (
            <GameCard
              key={game.matchup_id}
              game={game}
              variant="secondary"
              byeTeamIds={byeTeamIds}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Bracket section card ──────────────────────────────────────────────────────

function BracketSection({
  title,
  bracket,
  eyebrow,
}: {
  title: string;
  bracket: BracketSection;
  eyebrow?: string;
}) {
  if (!bracket.rounds.length) return null;
  const byeTeamIds = new Set(bracket.bye_teams.map((t) => t.team_id));
  const nRounds = bracket.rounds.length;

  return (
    <Card>
      <CardHeader eyebrow={eyebrow ?? `${bracket.size} teams`} title={title} />
      <div className="p-5 pt-4">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${nRounds}, 1fr)`,
            gap: "1.25rem",
          }}
        >
          {bracket.rounds.map((round, i) => (
            <RoundColumn
              key={round.round_num}
              round={round}
              isFirst={i === 0}
              isLast={i === nRounds - 1}
              byeTeamIds={byeTeamIds}
            />
          ))}
        </div>
      </div>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function PlayoffsPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: seasonId ? qk.bracket(seasonId) : ["bracket", "none"],
    queryFn: () => fetchBracket(seasonId as number),
    enabled: seasonId != null,
  });
  // Power as of playoff entry = the default (end-of-regular-season) ranking.
  const power = usePower(seasonId);

  return (
    <div className="dz-rise space-y-5">
      <div>
        <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Playoffs</h1>
      </div>

      {isLoading && <Skeleton className="h-96 w-full" />}

      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data && !data.available && (
        <Card>
          <CardHeader eyebrow={`season ${data.season_year}`} title="Postseason matchups" />
          <div className="p-5">
            <DataGap reason={data.reason ?? "bracket_unavailable"} />
          </div>
        </Card>
      )}

      {data?.available && (
        <div className="space-y-5">
          {data.playoff_bracket && (
            <BracketSection
              title="Championship Bracket"
              bracket={data.playoff_bracket}
              eyebrow={`${data.playoff_bracket.size} teams`}
            />
          )}

          {data.consolation_bracket && (
            <BracketSection
              title="Consolation Bracket"
              bracket={data.consolation_bracket}
              eyebrow={`${data.consolation_bracket.size} teams`}
            />
          )}

          {!data.consolation_bracket && data.playoff_bracket && (
            <Card>
              <CardHeader eyebrow="consolation bracket" title="Consolation" />
              <div className="p-5">
                <DataGap reason="consolation_indistinguishable" />
              </div>
            </Card>
          )}

          {data.caveat && (
            <p className="px-1 text-[var(--fs-xs)] text-faint">{data.caveat}</p>
          )}

          {power.data && power.data.rows.length > 0 && (
            <Card>
              <CardHeader
                eyebrow="who entered the bracket strongest · all-play adjusted"
                title="Power at playoff entry"
                action={
                  <Link to="/standings?lens=power" className="text-[var(--fs-sm)] text-accent hover:underline">
                    week-by-week lens →
                  </Link>
                }
              />
              <PowerTable data={power.data} />
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
