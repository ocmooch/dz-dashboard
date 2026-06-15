/**
 * Inline injury designation, shared by the box score and the week-scoped team
 * roster so a player reads identically on both. Pure presentation: the backend
 * (`analytics/injuries.py`) decides what counts as a real status / body part /
 * practice code — this only renders the fields it's handed.
 *
 * Renders only for a real game designation (Out / Doubtful / Questionable /
 * Probable); practice-only reports arrive with `status == null` and show nothing.
 */

const SHORT_STATUS: Record<string, string> = { Questionable: "Q", Doubtful: "D" };

const PRACTICE_SENTENCE: Record<string, string> = {
  DNP: "Did not participate in practice",
  Ltd: "Limited participation in practice",
  Full: "Full participation in practice",
  Out: "Ruled out at practice",
};

export interface InjuryBadgeProps {
  status: string;
  bodyPart?: string | null;
  secondary?: string | null;
  practiceStatus?: string | null;
}

export function InjuryBadge({ status, bodyPart, secondary, practiceStatus }: InjuryBadgeProps) {
  const short = SHORT_STATUS[status] ?? status;
  // "Out" already implies a missed practice, so don't repeat it as a practice code.
  const showPractice = !!practiceStatus && !(status === "Out" && practiceStatus === "Out");

  const bodyInline = bodyPart
    ? secondary
      ? `${bodyPart}/${secondary}`
      : bodyPart
    : null;
  const parts = [short, bodyInline, showPractice ? practiceStatus : null].filter(Boolean);
  const label = parts.join(" · ");

  const bodyFull = bodyPart ? (secondary ? `${bodyPart} / ${secondary}` : bodyPart) : null;
  const tooltip = [
    bodyFull ? `${status} — ${bodyFull}.` : `${status}.`,
    showPractice ? `${PRACTICE_SENTENCE[practiceStatus] ?? practiceStatus}.` : null,
  ]
    .filter(Boolean)
    .join(" ");

  const color = status === "Out" || status === "Doubtful" ? "var(--loss)" : "var(--warn)";
  return (
    <span className="ml-1 text-[var(--fs-xs)]" style={{ color }} title={tooltip}>
      {label}
    </span>
  );
}
