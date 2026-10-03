import { useEffect, useRef, useState } from "react";

import { IconAlertTriangle, IconLoader2, IconX, IconZoomScan } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { getJob, lookHarder } from "@/lib/api";
import type { PipelineJob } from "@/types/jobs";

/** How often a running Look harder job is polled. */
export const LOOK_HARDER_POLL_MS = 2000;

interface Props {
  immichAssetId: string | null;
  available: boolean;
  onFinished: (message: string) => void;
}

/**
 * Re-detects one photo with the slower, open-vocabulary detector (issue
 * #390) -- Repair for a dog YOLO keeps missing. Runs as a background job
 * that can take minutes on CPU, so this polls it and shows its state until
 * it finishes, then hands the result message to the page to refresh.
 *
 * Destructive like Repair (replaces this photo's detections and any review
 * recorded for them), so it uses the same inline-confirm pattern.
 */
export function LookHarderButton({ immichAssetId, available, onFinished }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState<PipelineJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Read through a ref so a parent re-render (a new callback identity, e.g.
  // on detection hover) doesn't restart the poll timer.
  const onFinishedRef = useRef(onFinished);

  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  useEffect(() => {
    if (!job) {
      return;
    }

    let cancelled = false;

    const timer = window.setTimeout(async () => {
      try {
        const next = await getJob(job.id);

        if (cancelled) {
          return;
        }

        if (next.status === "completed") {
          setJob(null);
          onFinishedRef.current(next.progress_message ?? "Look harder finished.");
        } else if (next.status === "failed" || next.status === "canceled") {
          setJob(null);
          setError(
            next.error_message ??
              (next.status === "canceled" ? "Look harder was canceled." : "Look harder failed."),
          );
        } else {
          setJob(next);
        }
      } catch (err) {
        if (!cancelled) {
          setJob(null);
          setError(err instanceof Error ? err.message : "Lost track of Look harder");
        }
      }
    }, LOOK_HARDER_POLL_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // Re-armed by every poll result: setJob(next) is a new object.
  }, [job]);

  if (!immichAssetId) {
    return null;
  }

  const start = async () => {
    setError(null);
    setStarting(true);

    try {
      const queued = await lookHarder(immichAssetId);
      setConfirming(false);
      setJob(queued);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start Look harder");
    } finally {
      setStarting(false);
    }
  };

  if (job) {
    return (
      <div className="flex flex-wrap items-center gap-2" role="status">
        <Button variant="destructive" size="sm" disabled>
          <IconLoader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Looking harder…
        </Button>

        <span className="text-sm text-muted-foreground">
          {job.status === "pending"
            ? "Queued. Waiting for any running job to finish."
            : (job.progress_message ?? "Running.")}
        </span>
      </div>
    );
  }

  if (confirming) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-destructive/50 bg-destructive/5 px-2 py-1.5">
        <IconAlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />

        <span className="text-sm text-muted-foreground">
          Re-detects this photo with a slower, more thorough detector. This can take several
          minutes, replaces its current detections (even if nothing is found), and discards any
          review recorded for it. Continue?
        </span>

        <Button variant="destructive" size="sm" onClick={start} disabled={starting}>
          <IconZoomScan className="h-4 w-4" aria-hidden="true" />
          {starting ? "Starting…" : "Yes, look harder"}
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setConfirming(false)}
          disabled={starting}
        >
          <IconX className="h-4 w-4" aria-hidden="true" />
          Cancel
        </Button>

        {error && <p className="w-full text-sm text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="destructive"
        size="sm"
        onClick={() => setConfirming(true)}
        disabled={!available}
        title={available ? undefined : "Look harder isn't available in this install"}
      >
        <IconZoomScan className="h-4 w-4" aria-hidden="true" />
        Look harder
      </Button>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
