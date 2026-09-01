import { useEffect } from "react";

import { IconSparkles } from "@tabler/icons-react";
import { cn } from "@/lib/utils";

interface Props {
  /** The reviewed count just reached (a positive multiple of 10), or null to show nothing. */
  milestone: number | null;
  onDismiss: () => void;
}

const DISMISS_AFTER_MS = 2200;

/**
 * A brief, non-blocking toast for every 10th classification reviewed
 * (docs/specs/review-tab-engagement-and-layout.md). Fixed-position and
 * pointer-events-none so it never sits in the way of the keyboard-driven
 * review flow, and it dismisses itself -- no confirmation, nothing to click.
 */
export function ReviewMilestoneCelebration({ milestone, onDismiss }: Props) {
  useEffect(() => {
    if (milestone === null) {
      return;
    }

    const timer = window.setTimeout(onDismiss, DISMISS_AFTER_MS);

    return () => window.clearTimeout(timer);
  }, [milestone, onDismiss]);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed right-4 top-4 z-50"
    >
      {milestone !== null && (
        <div
          role="status"
          className={cn(
            "flex items-center gap-2 rounded-full border bg-card px-4 py-2 text-sm font-medium text-card-foreground shadow-lg ring-1 ring-foreground/10",
            "motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95 motion-safe:slide-in-from-top-2",
            "motion-reduce:animate-in motion-reduce:fade-in",
          )}
        >
          <IconSparkles className="h-4 w-4 text-chart-4" aria-hidden="true" />
          {milestone} reviewed — nice streak!
        </div>
      )}
    </div>
  );
}
