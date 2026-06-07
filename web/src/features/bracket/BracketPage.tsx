import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type Bracket = Awaited<ReturnType<typeof fetchBracket>>;
type BracketGame = Bracket["weeks"][number]["games"][number];

async function fetchBracket(seasonId: number) {
  const { data, error } = await api.GET("/v1/seasons/{season_id}/bracket", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load bracket");
  return data.data;
}

function GameLabel({ game }: { game: BracketGame }) {
  if (game.is_consolation === true) return <Badge variant="gap">consolation</Badge>;
  if (game.is_consolation === false) return <Badge variant="accent">playoff</Badge>;
  return <Badge variant="gap">postseason</Badge>;
}

function TeamLine({ team }: { team: NonNullable<BracketGame["team_a"]> }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-1)] px-3 py-2">
      <Chip name={team.owner_name} sub={team.team_name ?? undefined} />
      <span className={`num text-[var(--fs-lg)] ${team.is_winner ? "text-win" : "text-muted"}`}>
        {team.score != null ? num(team.score) : "—"}
      </span>
    </div>
  );
}

function GameCard({ game }: { game: BracketGame }) {
  return (
    <Link
      to={`/matchups/${game.matchup_id}`}
      className="block rounded-[var(--radius-sm)] border border-[var(--border)] p-3 transition-colors hover:border-[var(--accent)]"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <GameLabel game={game} />
        <span className="text-[var(--fs-xs)] text-faint">box score</span>
      </div>
      <div className="space-y-2">
        {game.team_a && <TeamLine team={game.team_a} />}
        {game.team_b && <TeamLine team={game.team_b} />}
      </div>
    </Link>
  );
}

export function BracketPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: seasonId ? qk.bracket(seasonId) : ["bracket", "none"],
    queryFn: () => fetchBracket(seasonId as number),
    enabled: seasonId != null,
  });

  return (
    <div className="dz-rise space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="dz-eyebrow mb-1">Season {current?.season_year ?? ""}</div>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Bracket</h1>
        </div>
        {data && <Badge variant="gap">source caveat</Badge>}
      </div>

      {data?.caveat && (
        <Card>
          <div className="p-5 text-[var(--fs-sm)] text-muted">{data.caveat}</div>
        </Card>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      )}
      {isError && <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />}

      {data && !data.available && (
        <Card>
          <CardHeader eyebrow={`season ${data.season_year}`} title="Postseason matchups" />
          <div className="p-5">
            <DataGap reason={data.reason ?? "bracket_unavailable"} />
          </div>
        </Card>
      )}

      {data?.available &&
        data.weeks.map((week) => (
          <Card key={week.week}>
            <CardHeader
              eyebrow={`after ${data.regular_season_weeks} regular-season weeks`}
              title={`Week ${week.week}`}
            />
            <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
              {week.games.map((game) => (
                <GameCard key={game.matchup_id} game={game} />
              ))}
            </div>
          </Card>
        ))}
    </div>
  );
}
