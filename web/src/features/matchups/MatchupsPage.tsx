import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Card, CardHeader, Chip, EmptyState, ErrorState, UNSCORED_SEASON_NOTE, Skeleton, WeekStepper } from "@/design-system";
import { MatchupFlags } from "@/features/matchups/MatchupFlags";
import { api } from "@/lib/api/client";
import { num, teamAvatarUrl } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type GameCard = NonNullable<
  Awaited<ReturnType<typeof fetchWeekMatchups>>
>["games"][number];

async function fetchWeekMatchups(seasonId: number, week: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/weeks/{week}/matchups", {
    params: { path: { season_id: seasonId, week } },
  });
  if (error || !data) throw new Error("Failed to load matchups");
  return data.data;
}

async function fetchSeasonSummary(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load season");
  return data.data;
}

function TeamSide({
  team,
  align,
  margin,
}: {
  team: GameCard["team_a"];
  align: "left" | "right";
  margin: number | null | undefined;
}) {
  if (!team) return <div className="text-faint">Bye</div>;
  const winner = team.is_winner;
  const signedMargin = margin == null ? null : winner ? margin : -margin;
  return (
    <div className={`flex items-center gap-3 ${align === "right" ? "flex-row-reverse text-right" : ""}`}>
      <Chip name={team.team_name ?? team.owner_name} sub={team.owner_name ?? undefined} avatarUrl={teamAvatarUrl(team.team_id)} />
      <span className="flex flex-col">
        <span className={`num text-[var(--fs-h2)] font-bold ${winner ? "text-win" : "text-muted"}`}>
          {num(team.score)}
        </span>
        {signedMargin != null && (
          <span className={`num text-[var(--fs-xs)] ${signedMargin > 0 ? "text-win" : signedMargin < 0 ? "text-loss" : "text-muted"}`}>
            {signedMargin > 0 ? "+" : ""}
            {num(signedMargin)}
          </span>
        )}
      </span>
    </div>
  );
}

/** Eyebrow text reflecting the postseason tier (championship/consolation are
 *  differentiated from a generic playoff game; consolation is never "playoff"). */
function eyebrowFor(game: GameCard): string {
  if (game.bracket_tier === "championship") return "championship";
  if (game.bracket_tier === "consolation") return "consolation";
  if (game.is_playoff) return "playoff";
  return "regular season";
}

function GameCardView({ game }: { game: GameCard }) {
  return (
    <Link
      to={`/matchups/${game.matchup_id}`}
      className="block rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-1)] p-4 transition-colors hover:border-[var(--accent)]"
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <span className="dz-eyebrow shrink-0 pt-1">{eyebrowFor(game)}</span>
        <MatchupFlags flags={game.flags} className="justify-end" />
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <TeamSide team={game.team_a} align="left" margin={game.margin} />
        <span className="font-display text-[var(--fs-sm)] text-faint">vs</span>
        <TeamSide team={game.team_b} align="right" margin={game.margin} />
      </div>
    </Link>
  );
}

export function MatchupsPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const [params, setParams] = useSearchParams();
  const week = Math.max(1, Number(params.get("week") ?? "1") || 1);

  const summary = useQuery({
    queryKey: seasonId ? ["season-summary", seasonId] : ["season-summary", "none"],
    queryFn: () => fetchSeasonSummary(seasonId as number),
    enabled: seasonId != null,
  });
  const maxWeek =
    (summary.data?.regular_season_weeks ?? 0) + (summary.data?.playoff_weeks ?? 0) || 18;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: seasonId ? qk.weekMatchups(seasonId, week) : ["matchups", "none"],
    queryFn: () => fetchWeekMatchups(seasonId as number, week),
    enabled: seasonId != null,
  });

  const setWeek = (w: number) => {
    params.set("week", String(w));
    setParams(params, { replace: true });
  };

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Matchups</h1>
        </div>
        <WeekStepper week={week} max={maxWeek} onChange={setWeek} />
      </div>

      {data && !data.is_scored && (
        <Badge variant="gap">{UNSCORED_SEASON_NOTE}</Badge>
      )}

      <Card>
        <CardHeader eyebrow={`week ${week}`} title="Games" />
        {isLoading && (
          <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        )}
        {isError && <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />}
        {data && data.games.length === 0 && (
          <EmptyState title="No games this week" hint="Try another week with the stepper above." />
        )}
        {data && data.games.length > 0 && (
          <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2">
            {data.games.map((g) => (
              <GameCardView key={g.matchup_id} game={g} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
