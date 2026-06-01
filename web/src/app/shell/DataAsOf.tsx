import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

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
  const ok = run?.status === "success";
  return (
    <Link
      to="/about"
      className="dz-data-status"
      title="Data coverage & sources"
      aria-label={`Data as of ${when}${run?.run_id != null ? `, run ${run.run_id}` : ""} — open coverage`}
    >
      <span className={`dz-live-dot ${ok ? "" : "dz-live-dot--warn"}`.trim()} aria-hidden />
      <span className="text-right leading-tight">
        <span className="dz-eyebrow block">data as of</span>
        <span className="num block text-[var(--fs-sm)] text-muted">
          {when}
          {run?.run_id != null && <span className="text-faint"> · run #{run.run_id}</span>}
        </span>
      </span>
    </Link>
  );
}
