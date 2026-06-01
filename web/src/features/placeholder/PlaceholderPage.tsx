import { EmptyState } from "@/design-system";

/** Honest placeholder for nav destinations landing in later milestones (P5–P9). */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="dz-rise">
      <EmptyState title={`${title} — coming soon`} hint="This view lands in a later Phase 2 milestone." />
    </div>
  );
}
