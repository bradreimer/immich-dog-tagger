import { useState } from "react";

import { IconAlertTriangle, IconTool, IconX } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { repairDerivedData } from "@/lib/api";
import type { DerivedDataRepairResult, DerivedDataStatus } from "@/types/diagnostics";

interface Props {
  status: DerivedDataStatus;
  onRepaired: () => void;
}

/**
 * Batch-runs DerivedDataService.repair() (issue #194/#323) over every
 * currently missing download/crop file (docs/specs/broken-crop-auto-repair.md).
 * Scoped to missing_downloads/missing_crops -- the two categories repair()
 * actually fixes -- rather than total_missing, since missing embedding
 * sources have no automatic fix (they still need a human to re-run
 * learn/import-review).
 */
export function DerivedDataRepairAction({ status, onRepaired }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [repairing, setRepairing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DerivedDataRepairResult | null>(null);
  // Captured when the confirm dialog opens, so the result message can report
  // "before -> after" rather than just an attempt count (see the analogous
  // StaleDetectionRepairAction rationale, #282/#293).
  const [beforeEligible, setBeforeEligible] = useState<number | null>(null);

  const repairEligible = status.missing_downloads + status.missing_crops;

  // A fully successful repair flips repairEligible to 0, which would
  // otherwise unmount this whole component (and the result it just posted)
  // before the owner can read it -- so a still-fresh `result` keeps it
  // mounted for at least the trailing summary line.
  if (repairEligible === 0 && !result) {
    return null;
  }

  const repair = async () => {
    setError(null);
    setRepairing(true);

    try {
      const outcome = await repairDerivedData();
      setResult(outcome);
      setConfirming(false);
      onRepaired();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to repair derived data");
    } finally {
      setRepairing(false);
    }
  };

  const resultSummary = result && beforeEligible !== null && (() => {
    const actualDrop = beforeEligible - repairEligible;
    const short = result.total_repaired > 0 && actualDrop < result.total_repaired;

    return (
      <p
        className={`w-full text-xs ${short ? "font-medium text-status-warning" : "text-muted-foreground"}`}
      >
        Repaired {result.total_repaired} ({result.downloads_repaired} download
        {result.downloads_repaired === 1 ? "" : "s"}, {result.crops_repaired} crop
        {result.crops_repaired === 1 ? "" : "s"}), failed {result.failed} —{" "}
        {beforeEligible} → {repairEligible} still missing
        {short && " (fewer than expected -- may need investigation)"}.
      </p>
    );
  })();

  if (repairEligible === 0) {
    return <div className="rounded-md border p-3">{resultSummary}</div>;
  }

  if (confirming) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 space-y-3">
        <div className="flex items-start gap-2">
          <IconAlertTriangle className="h-4 w-4 shrink-0 text-destructive mt-0.5" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            Repairs {repairEligible} missing derived file{repairEligible === 1 ? "" : "s"} by
            re-downloading or re-detecting as needed.{" "}
            {status.reviewed_at_risk > 0 && (
              <>
                <span className="font-medium">{status.reviewed_at_risk}</span> of the affected
                photo{status.reviewed_at_risk === 1 ? "" : "s"} {status.reviewed_at_risk === 1 ? "has" : "have"}{" "}
                recorded review history that will be discarded and re-classified from scratch.
              </>
            )}
          </p>
        </div>

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
        <span className="font-medium">{repairEligible} file{repairEligible === 1 ? "" : "s"}</span>{" "}
        missing (downloads/crops) and ready to repair.
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          setResult(null);
          setBeforeEligible(repairEligible);
          setConfirming(true);
        }}
      >
        <IconTool className="h-4 w-4" aria-hidden="true" />
        Repair
      </Button>
      {resultSummary}
    </div>
  );
}
