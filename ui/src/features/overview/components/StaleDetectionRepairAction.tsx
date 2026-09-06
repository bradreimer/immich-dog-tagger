import { useState } from "react";

import { IconAlertTriangle, IconTool, IconX } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { repairStaleDetections } from "@/lib/api";
import type { StaleDetectionRepairResult, StaleDetectionStatus } from "@/types/diagnostics";

interface Props {
  status: StaleDetectionStatus;
  onRepaired: () => void;
}

/**
 * Batch-runs the per-photo Repair action (issue #226) over every photo
 * flagged as having a stale (EXIF-orientation) detection
 * (docs/specs/stale-detection-auto-repair.md). Reviewed photos are excluded
 * by default -- repairing one discards its review history -- and including
 * them requires an explicit, informed opt-in via the switch below, not a
 * hidden default.
 */
export function StaleDetectionRepairAction({ status, onRepaired }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [includeReviewed, setIncludeReviewed] = useState(false);
  const [repairing, setRepairing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StaleDetectionRepairResult | null>(null);

  if (status.healthy) {
    return null;
  }

  const repair = async () => {
    setError(null);
    setRepairing(true);

    try {
      const outcome = await repairStaleDetections(includeReviewed);
      setResult(outcome);
      setConfirming(false);
      onRepaired();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to repair stale detections");
    } finally {
      setRepairing(false);
    }
  };

  if (confirming) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 space-y-3">
        <div className="flex items-start gap-2">
          <IconAlertTriangle className="h-4 w-4 shrink-0 text-destructive mt-0.5" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            Re-detects {status.flagged} photo{status.flagged === 1 ? "" : "s"} with stale
            detections. {status.reviewed_at_risk > 0 && (
              <>
                <span className="font-medium">{status.reviewed_at_risk}</span> of these{" "}
                {status.reviewed_at_risk === 1 ? "has" : "have"} recorded review history that
                will only be repaired if you include it below.
              </>
            )}
          </p>
        </div>

        {status.reviewed_at_risk > 0 && (
          <div className="flex items-center justify-between gap-3 rounded-md border p-2">
            <span className="text-sm">
              Also repair the {status.reviewed_at_risk} reviewed photo{status.reviewed_at_risk === 1 ? "" : "s"}
              , discarding its review history
            </span>
            <Switch
              aria-label="Also repair reviewed photos, discarding their review history"
              checked={includeReviewed}
              disabled={repairing}
              onCheckedChange={setIncludeReviewed}
            />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="destructive" size="sm" onClick={repair} disabled={repairing}>
            <IconTool className="h-4 w-4" aria-hidden="true" />
            {repairing ? "Repairing…" : "Yes, repair"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirming(false)}
            disabled={repairing}
          >
            <IconX className="h-4 w-4" aria-hidden="true" />
            Cancel
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-status-warning/40 bg-status-warning/5 p-3">
      <IconAlertTriangle className="h-4 w-4 shrink-0 text-status-warning" aria-hidden="true" />
      <p className="text-sm">
        <span className="font-medium">{status.flagged} photo{status.flagged === 1 ? "" : "s"}</span>{" "}
        have stale detections from an old EXIF-orientation bug.
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          setResult(null);
          setConfirming(true);
        }}
      >
        <IconTool className="h-4 w-4" aria-hidden="true" />
        Repair
      </Button>
      {result && (
        <p className="w-full text-xs text-muted-foreground">
          Repaired {result.repaired}, skipped {result.skipped_reviewed} reviewed, failed{" "}
          {result.failed}.
        </p>
      )}
    </div>
  );
}
