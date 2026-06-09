import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type LeagueStories = components["schemas"]["LeagueStories"];
type StoryCard = components["schemas"]["StoryCard"];

async function fetchStories(): Promise<LeagueStories> {
  const { data, error } = await api.GET("/v1/league/stories");
  if (error || !data) throw new Error("league stories");
  return data.data;
}

function storySubject(story: StoryCard) {
  if (story.primary_team) {
    return <Chip name={story.primary_team.team_name ?? story.primary_team.owner_name} sub={story.primary_team.owner_name ?? undefined} />;
  }
  if (story.primary_owner) {
    return <Chip name={story.primary_owner.display_name} />;
  }
  return null;
}

export function StoriesPage() {
  const stories = useQuery({ queryKey: qk.leagueStories, queryFn: fetchStories });

  if (stories.isError) {
    return <ErrorState message="Could not load league stories." onRetry={() => stories.refetch()} />;
  }

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Argument starter</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Stories</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          Backend-computed league memories: blowouts, painful beats, close-loss patterns, and team-name
          artifacts. Each card says when the data is not available.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {stories.isLoading &&
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton className="m-5 h-36" />
            </Card>
          ))}
        {stories.data?.stories.map((story) => (
          <Card key={story.story_id}>
            <CardHeader
              eyebrow={story.available ? `${story.season_year ?? "all-time"}${story.week ? ` week ${story.week}` : ""}` : "gap"}
              title={story.title}
              action={
                story.matchup_id ? (
                  <Link to={`/matchups/${story.matchup_id}`} className="dz-badge dz-badge--accent">
                    Box score
                  </Link>
                ) : undefined
              }
            />
            <div className="space-y-4 p-5">
              {story.available ? (
                <>
                  <div className="grid grid-cols-[1fr_auto] items-center gap-4">
                    <div>{storySubject(story)}</div>
                    <Stat
                      label={story.metric_label}
                      value={story.metric_value == null ? "-" : num(Number(story.metric_value), 2)}
                      tone="accent"
                    />
                  </div>
                  {story.secondary_team && (
                    <div className="text-[var(--fs-sm)] text-muted">
                      Against{" "}
                      <span className="font-semibold text-text">
                        {story.secondary_team.team_name ?? story.secondary_team.owner_name}
                      </span>
                    </div>
                  )}
                  {"items" in story && Array.isArray(story.items) && (
                    <div className="space-y-2">
                      {story.items.map((item: { team_name?: string; seasons?: number }) => (
                        <div
                          key={item.team_name}
                          className="flex items-center justify-between rounded-[var(--radius-sm)] bg-[var(--surface-2)] px-3 py-2"
                        >
                          <span className="font-semibold">{item.team_name}</span>
                          <Badge variant="accent">{item.seasons} seasons</Badge>
                        </div>
                      ))}
                    </div>
                  )}
                  {story.caveat && <p className="text-[var(--fs-xs)] text-faint">{story.caveat}</p>}
                </>
              ) : (
                <DataGap reason={story.reason ?? undefined} />
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
