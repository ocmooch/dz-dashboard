import { num } from "@/lib/format";

type PlayerScoreCellProps = {
  points: number | null | undefined;
  zeroReason?: string | null;
  zeroDetail?: string | null;
  zeroLabel?: string | null;
  injuryBodyPart?: string | null;
  muted?: boolean;
};

export function PlayerScoreCell({
  points,
  zeroReason,
  zeroDetail,
  zeroLabel,
  injuryBodyPart,
  muted = false,
}: PlayerScoreCellProps) {
  const value = num(points);
  if (zeroReason === "bye" || zeroReason === "did_not_play") {
    const label = zeroLabel ?? (zeroReason === "bye" ? "Bye" : "DNP");
    const injuryDetail = injuryBodyPart ? ` - ${injuryBodyPart}` : "";
    const title =
      zeroReason === "bye"
        ? "On bye - did not play"
        : `Did not play (inactive / injury / scratch)${injuryDetail}`;
    return (
      <span className="dz-eyebrow text-faint" title={title}>
        {label}
      </span>
    );
  }
  if (zeroReason === "unexpected") {
    return (
      <span
        className="inline-flex items-center justify-end gap-1 text-loss"
        title={zeroDetail ?? "Unexpectedly 0 - reason unclear"}
      >
        {value}
        <span aria-label="unexpectedly zero" className="dz-eyebrow">
          !
        </span>
      </span>
    );
  }
  return <span className={muted ? "text-muted" : "text-text"}>{value}</span>;
}
