/**
 * Player status timeline (Sleeper D7). Pure presentation over `/v1/players/{id}/status`: the BFF
 * decides which report or snapshot describes each week and what counts as a gap.
 *
 * Columns: the official weekly game report, and (on seasons with platform snapshots) the newest
 * capture before kickoff. "—" in the report column means "not on the report", a real answer.
 */
import { useQuery } from "@tanstack/react-query";

import { InjuryBadge } from "@/components/InjuryBadge";
import { CapabilityGate, DataGap, ProvenanceNote, Skeleton } from "@/design-system";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { capabilityGapText, provenanceText, statusSnapshotHeading, statusSnapshotNote } from "@/lib/platform";
import { qk } from "@/lib/queryKeys";

type StatusEntry = components["schemas"]["StatusEntry"];
export type PlayerStatusTimeline = components["schemas"]["PlayerStatusTimeline"];

async function fetchStatus(id: number, season: number) {
  const { data, error } = await api.GET("/v1/players/{player_id}/status", {
    params: { path: { player_id: id }, query: { season } },
  });
  if (error || !data) throw new Error("Failed to load player status");
  return data.data;
}

function EntryCell({ entry }: { entry: StatusEntry }) {
  const parts: string[] = [];
  if (entry.roster_status) parts.push(entry.roster_status);
  if (entry.depth_chart) parts.push(entry.depth_chart);
  return (
    <span>
      {entry.injury_status ? (
        <InjuryBadge
          status={entry.injury_status}
          bodyPart={entry.injury_body_part}
          secondary={entry.injury_secondary}
          practiceStatus={entry.injury_practice_status}
          source={entry.source}
          asOf={entry.as_of}
        />
      ) : null}
      {parts.length > 0 && <span className="ml-1 text-[var(--fs-xs)] text-muted">{parts.join(" · ")}</span>}
      {!entry.injury_status && parts.length === 0 && <span className="text-faint">healthy</span>}
      {entry.as_of && <span className="ml-2 font-mono text-[var(--fs-xs)] text-faint">{entry.as_of}</span>}
    </span>
  );
}

export function StatusTimelineView({ data }: { data: PlayerStatusTimeline }) {
  if (!data.available) {
    return (
      <div className="p-5">
        <DataGap reason={data.reason ?? undefined} />
      </div>
    );
  }
  const heading = statusSnapshotHeading(data.platform);
  return (
    <div className="space-y-3 p-5">
      {data.latest && (
        <div className="rounded border border-[var(--hairline)] p-3" data-testid="status-latest">
          <div className="dz-eyebrow mb-1">Latest · {heading}</div>
          <EntryCell entry={data.latest} />
        </div>
      )}
      {!data.has_snapshots && (
        <CapabilityGate
          capKey="player_status_daily"
          cap={data.snapshot_capability}
          platform={data.platform}
          size="sm"
        >
          {/* Partial (weekly reports only): say so once, not per week. */}
          <ProvenanceNote>
            {provenanceText("player_status_daily", data.platform) ??
              capabilityGapText("player_status_daily", data.snapshot_capability, data.platform)}
          </ProvenanceNote>
        </CapabilityGate>
      )}
      <div className="overflow-x-auto">
        <table className="dz-table">
          <thead>
            <tr>
              <th>Week</th>
              <th>Game status</th>
              {data.has_snapshots && <th>{heading}</th>}
            </tr>
          </thead>
          <tbody>
            {data.weeks.map((w) => (
              <tr key={w.week}>
                <td className="num text-faint">wk{w.week}</td>
                <td>
                  {w.game_report ? (
                    <EntryCell entry={w.game_report} />
                  ) : w.game_report_gap ? (
                    <DataGap reason={w.game_report_gap} size="sm" />
                  ) : (
                    <span className="text-faint" title="Not on that week's injury report">
                      —
                    </span>
                  )}
                </td>
                {data.has_snapshots && (
                  <td>
                    {w.snapshot ? (
                      <EntryCell entry={w.snapshot} />
                    ) : (
                      <DataGap reason={w.snapshot_gap ?? undefined} size="sm" />
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.has_snapshots && <ProvenanceNote>{statusSnapshotNote(data.platform)}</ProvenanceNote>}
      {data.is_provisional && <ProvenanceNote>Season in progress; subject to change.</ProvenanceNote>}
    </div>
  );
}

export function StatusTimeline({ playerId, season }: { playerId: number; season: number }) {
  const { data, isLoading } = useQuery({
    queryKey: qk.playerStatus(playerId, season),
    queryFn: () => fetchStatus(playerId, season),
  });
  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!data) return null;
  return <StatusTimelineView data={data} />;
}
