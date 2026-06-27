import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSeasons } from "@/app/shell/SeasonContext";
import { Badge, Card, CardHeader, EmptyState, ErrorState, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

// The Insights Lab is the non-viz parallel to the Viz Lab: a holding space for
// "insight primitives" — structured findings the BFF computes from existing metrics
// and serves as text. The narration prose is built (server-side) only from the facts
// shown beneath it, so the page stays pure presentation — it neither computes a number
// nor decides which finding to tell. Adding the next insight is another card here.

async function fetchInsights(seasonId: number) {
  const { data, error } = await api.GET("/v1/lab/insights/{season_id}", {
    params: { path: { season_id: seasonId } },
  });
  if (error || !data) throw new Error("Failed to load insights");
  return data.data;
}

type Insights = Awaited<ReturnType<typeof fetchInsights>>;
type Insight = Insights["insights"][number];

const CONFIDENCE_VARIANT: Record<string, "accent" | undefined> = { high: "accent" };

/** One insight: headline, the narrated finding, then the numbers it was built from. */
function InsightCard({ insight }: { insight: Insight }) {
  const subject = insight.subject;
  return (
    <Card>
      <CardHeader
        eyebrow="insight"
        title={insight.title}
        action={
          <Badge variant={CONFIDENCE_VARIANT[insight.confidence]}>
            {insight.confidence} confidence
          </Badge>
        }
      />
      <div className="space-y-4 p-5">
        <p className="max-w-2xl text-[var(--fs-md)] leading-relaxed text-text">
          {insight.narration}
        </p>

        <div className="flex flex-wrap gap-2">
          {insight.facts.map((f) => (
            <span
              key={f.label}
              className="inline-flex items-baseline gap-1.5 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1"
            >
              <span className="dz-eyebrow text-faint">{f.label}</span>
              <span className="num text-[var(--fs-sm)] font-semibold text-text">
                {f.value}
                {f.unit ? <span className="ml-0.5 text-faint">{f.unit}</span> : null}
              </span>
            </span>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-2 text-[var(--fs-xs)] text-faint">
          <span>
            Source: <span className="num">{insight.provenance.metric}</span> ·{" "}
            <span className="num">{insight.provenance.endpoint}</span>
          </span>
          {subject?.owner_id != null && (
            <Link to={`/managers/${subject.owner_id}`} className="text-accent hover:underline">
              {subject.owner_name ?? "View manager"} →
            </Link>
          )}
        </div>
      </div>
    </Card>
  );
}

export function InsightsLabPage() {
  const { current } = useSeasons();
  const seasonId = current?.season_id;

  const insights = useQuery({
    queryKey: seasonId ? qk.labInsights(seasonId) : ["lab", "insights", "none"],
    queryFn: () => fetchInsights(seasonId as number),
    enabled: seasonId != null,
  });

  return (
    <div className="dz-rise space-y-6">
      <div>
        <div className="dz-eyebrow mb-1">Experimental</div>
        <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">Insights Lab</h1>
        <p className="mt-2 max-w-2xl text-[var(--fs-sm)] text-muted">
          The non-visual parallel to the Viz Lab: findings the analytics layer computes and
          narrates as text, each number traceable to a tested metric. A narrator (a template
          today, a model later) only arranges the facts — it never computes one.
        </p>
      </div>

      {insights.isLoading && <Skeleton className="h-[180px] w-full" />}
      {insights.isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => insights.refetch()} />
      )}

      {insights.data && !insights.data.available && (
        <EmptyState
          title="No insights for this season yet"
          hint="The primitives found nothing to say — an unplayed season has no schedule luck or draft to read."
        />
      )}

      {insights.data?.available && (
        <>
          {insights.data.notes.length > 0 && (
            <div className="space-y-1">
              {insights.data.notes.map((note) => (
                <p key={note} className="max-w-2xl text-[var(--fs-xs)] text-faint">
                  {note}
                </p>
              ))}
            </div>
          )}
          {insights.data.insights.map((insight) => (
            <InsightCard key={insight.kind} insight={insight} />
          ))}
        </>
      )}
    </div>
  );
}
