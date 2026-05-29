import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { qk } from "@/lib/queryKeys";

async function fetchMeta() {
  const { data, error } = await api.GET("/v1/meta");
  if (error || !data) throw new Error("meta");
  return data.data;
}

/** The "data as of … · run #" indicator, sourced from /v1/meta. */
export function DataAsOf() {
  const { data } = useQuery({ queryKey: qk.meta, queryFn: fetchMeta });
  const run = data?.latest_run;
  const finished = run?.finished_at ? new Date(run.finished_at) : null;
  const when = finished
    ? finished.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : "—";
  return (
    <div className="flex items-center gap-2 text-right">
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: run?.status === "success" ? "var(--win)" : "var(--warn)" }}
        aria-hidden
      />
      <div className="leading-tight">
        <div className="dz-eyebrow">data as of</div>
        <div className="num text-[var(--fs-sm)] text-muted">
          {when}
          {run?.run_id != null && <span className="text-faint"> · run #{run.run_id}</span>}
        </div>
      </div>
    </div>
  );
}
