import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Badge, Card, CardHeader, Chip, DataGap, ErrorState, Skeleton, Stat } from "@/design-system";
import { api } from "@/lib/api/client";
import { num } from "@/lib/format";
import { qk } from "@/lib/queryKeys";

type Meeting = {
  season_year?: number | null;
  week?: number | null;
  matchup_id?: number | null;
  a_score?: number;
  b_score?: number;
  margin_for_a?: number;
};

// HeadToHead is intentionally extra-permissive on the wire (each record carries
// its own context). The typed client only guarantees the envelope fields, so we
// widen here to read the pairwise stats the BFF computed.
type Pairwise = {
  owner_a: { owner_id: number; display_name?: string | null };
  owner_b: { owner_id: number; display_name?: string | null };
  available: boolean;
  reason?: string | null;
  games_played: number;
  a_wins?: number;
  b_wins?: number;
  ties?: number;
  a_win_pct?: number;
  avg_margin_for_a?: number;
  playoff_meetings?: number;
  highest_scoring_meeting?: Meeting;
  most_lopsided_meeting?: Meeting;
};

async function fetchPairwise(a: number, b: number): Promise<Pairwise> {
  const { data, error } = await api.GET(
    "/v1/owners/{owner_id}/head-to-head/{other_owner_id}",
    { params: { path: { owner_id: a, other_owner_id: b } } },
  );
  if (error || !data) throw new Error("Failed to load head-to-head");
  return data.data as unknown as Pairwise;
}

function MeetingLink({ meeting, children }: { meeting?: Meeting; children: React.ReactNode }) {
  if (!meeting) return <span className="text-faint">—</span>;
  const when = meeting.season_year ? `${meeting.season_year} · wk ${meeting.week}` : "—";
  const body = (
    <>
      <div className="num text-text">{children}</div>
      <div className="text-[var(--fs-xs)] text-faint">{when}</div>
    </>
  );
  return meeting.matchup_id != null ? (
    <Link to={`/matchups/${meeting.matchup_id}`} className="block hover:text-accent">
      {body}
    </Link>
  ) : (
    <div>{body}</div>
  );
}

export function PairwisePage() {
  const params = useParams();
  const a = Number(params.a);
  const b = Number(params.b);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.headToHead(a, b),
    queryFn: () => fetchPairwise(a, b),
    enabled: Number.isFinite(a) && Number.isFinite(b),
  });

  const aName = data?.owner_a.display_name ?? "Manager A";
  const bName = data?.owner_b.display_name ?? "Manager B";

  return (
    <div className="dz-rise space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <Link to="/rivalries" className="dz-eyebrow mb-1 inline-block hover:text-accent">
            ‹ Rivalry matrix
          </Link>
          <h1 className="font-display text-[var(--fs-h1)] font-bold tracking-wide">
            {aName} <span className="text-faint">vs</span> {bName}
          </h1>
        </div>
        {data?.available && (data.playoff_meetings ?? 0) > 0 && (
          <Badge variant="accent">{data.playoff_meetings} playoff meeting(s)</Badge>
        )}
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}
      {isError && (
        <ErrorState message="Could not reach the analytics service." onRetry={() => refetch()} />
      )}

      {data && !data.available && (
        <Card className="p-8">
          <DataGap reason={data.reason ?? "no_meetings"} />
          <p className="mt-3 text-[var(--fs-sm)] text-muted">
            {aName} and {bName} have no recorded games against each other.
          </p>
        </Card>
      )}

      {data && data.available && (
        <>
          <Card className="p-5">
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
              <Stat label={`${aName} wins`} value={data.a_wins ?? 0} tone="win" />
              <Stat label={`${bName} wins`} value={data.b_wins ?? 0} tone="loss" />
              <Stat label="Games" value={data.games_played} unit={data.ties ? `· ${data.ties} tie` : undefined} />
              <Stat
                label={`${aName} win %`}
                value={data.a_win_pct != null ? `${Math.round(data.a_win_pct * 100)}%` : "—"}
                tone="accent"
              />
            </div>
            <div className="mt-5 border-t border-[var(--hairline)] pt-4">
              <Stat
                label={`Avg margin (for ${aName})`}
                value={num(data.avg_margin_for_a ?? 0, 1)}
                unit="pts/game"
                tone={(data.avg_margin_for_a ?? 0) >= 0 ? "win" : "loss"}
              />
            </div>
          </Card>

          <Card>
            <CardHeader eyebrow="defining games" title="Notable Meetings" />
            <div className="grid grid-cols-1 gap-px bg-[var(--border)] sm:grid-cols-2">
              <div className="bg-[var(--surface-1)] p-5">
                <div className="dz-eyebrow mb-2">Highest-scoring meeting</div>
                <MeetingLink meeting={data.highest_scoring_meeting}>
                  {data.highest_scoring_meeting
                    ? `${num(data.highest_scoring_meeting.a_score)} – ${num(data.highest_scoring_meeting.b_score)}`
                    : "—"}
                </MeetingLink>
              </div>
              <div className="bg-[var(--surface-1)] p-5">
                <div className="dz-eyebrow mb-2">Most lopsided meeting</div>
                <MeetingLink meeting={data.most_lopsided_meeting}>
                  {data.most_lopsided_meeting
                    ? `${(data.most_lopsided_meeting.margin_for_a ?? 0) >= 0 ? "+" : ""}${num(data.most_lopsided_meeting.margin_for_a, 1)} for ${aName}`
                    : "—"}
                </MeetingLink>
              </div>
            </div>
          </Card>

          <div className="flex items-center gap-3">
            <Chip name={aName} />
            <span className="text-faint">vs</span>
            <Chip name={bName} />
          </div>
        </>
      )}
    </div>
  );
}
