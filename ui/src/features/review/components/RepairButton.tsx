import { useState } from "react";

import { IconAlertTriangle, IconTool, IconX } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { repairAsset } from "@/lib/api";
import type { AssetRepairResult } from "@/types/photoLookup";

interface Props {
  immichAssetId: string | null;
  onRepaired: (result: AssetRepairResult) => void;
}

/**
 * Forces one photo back through download/detect/classify (issue #226), for
 * when its detections look stale (predate the EXIF-orientation fix, #137)
 * rather than simply un-reviewed. Renders nothing without an asset id.
 *
 * Discards this photo's current Detection/Crop/CropClassification rows --
 * and, with them, any review already recorded against them -- so this asks
 * for confirmation before calling the API, the same inline-confirm pattern
 * DogManagementCard uses for merge.
 */
export function RepairButton({ immichAssetId, onRepaired }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [repairing, setRepairing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!immichAssetId) {
    return null;
  }

  const repair = async () => {
    setError(null);
    setRepairing(true);

    try {
      const result = await repairAsset(immichAssetId);
      setConfirming(false);
      onRepaired(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to repair photo");
    } finally {
      setRepairing(false);
    }
  };

  if (confirming) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-destructive/50 bg-destructive/5 px-2 py-1.5">
        <IconAlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />

        <span className="text-sm text-muted-foreground">
          Re-detects this photo and discards any review recorded for it. Continue?
        </span>

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

        {error && <p className="w-full text-sm text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <Button variant="destructive" size="sm" onClick={() => setConfirming(true)}>
      <IconTool className="h-4 w-4" aria-hidden="true" />
      Repair
    </Button>
  );
}
