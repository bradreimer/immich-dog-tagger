import { useEffect, useState } from "react";

import { IconSearch } from "@tabler/icons-react";

import {
  ClassificationNotFoundError,
  CropNotFoundError,
  PhotoLookupNotFoundError,
  assignCrop,
  assignDetection,
  correctClassification,
  correctSpecies,
  getDogs,
  getPhotoLookup,
  getSettings,
  markCropNotAnimal,
  unmarkCropNotAnimal,
} from "@/lib/api";
import { parseImmichAssetId } from "@/lib/immich";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { RepairButton } from "@/features/review/components/RepairButton";
import type { Dog } from "@/types/dogs";
import type { AssetRepairResult, PhotoLookupResult } from "@/types/photoLookup";

import { DetectionList } from "./components/DetectionList";
import { PhotoLookupImage } from "./components/PhotoLookupImage";

// Immich's exifInfo location fields (city/state/country), joined for
// display -- `null` when Immich genuinely has no GPS data for the photo,
// same meaning as on the Asset row itself. Surfaced here so a Repair-driven
// refresh of these fields (issue #326) is actually visible on this page.
function formatLocation(result: PhotoLookupResult): string | null {
  const parts = [result.city, result.state, result.country].filter(
    (part): part is string => Boolean(part),
  );

  return parts.length > 0 ? parts.join(", ") : null;
}

export function PhotoLookupPage() {
  const [urlInput, setUrlInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PhotoLookupResult | null>(null);
  const [identities, setIdentities] = useState<Dog[]>([]);
  const [repairMessage, setRepairMessage] = useState<string | null>(null);
  const [staleMessage, setStaleMessage] = useState<string | null>(null);
  const [hoveredDetectionId, setHoveredDetectionId] = useState<number | null>(null);
  const [showAccount, setShowAccount] = useState(false);

  useEffect(() => {
    getDogs()
      .then(setIdentities)
      .catch(() => setIdentities([]));

    // Only worth showing an account column when more than one is actually
    // configured (issue #346); a failed read just leaves it hidden.
    getSettings()
      .then((settings) => setShowAccount(settings.accounts.length > 1))
      .catch(() => setShowAccount(false));
  }, []);

  const runLookup = async (assetId: string) => {
    setError(null);
    setRepairMessage(null);
    setStaleMessage(null);
    setLoading(true);

    try {
      setResult(await getPhotoLookup(assetId));
    } catch (err) {
      setResult(null);
      setError(
        err instanceof PhotoLookupNotFoundError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to look up photo",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const assetId = new URLSearchParams(window.location.search).get("assetId");

    if (assetId) {
      void runLookup(assetId);
    }
    // Only ever read the query param that was present on initial load --
    // this page doesn't otherwise change the URL, so there's nothing to
    // react to after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    const assetId = parseImmichAssetId(urlInput);

    if (!assetId) {
      setError(
        "Paste a full Immich photo link, e.g. https://immich.example.com/photos/<id>.",
      );
      setResult(null);
      return;
    }

    await runLookup(assetId);
  };

  // A classification_id/crop_id this page already has in memory can be
  // deleted server-side by a Repair or the Overview "repair missing crops"
  // action reprocessing the same photo elsewhere (issue #356 hit the same
  // race in Review). Unlike Review's queue, Photo Lookup has nowhere to
  // drop the stale item to -- it's a single-photo view -- so the recovery
  // is to re-fetch this asset's current detections/crops/classifications
  // (fresh ids) and tell the owner why their action didn't apply, rather
  // than leaving a doomed classification_id/crop_id on screen for them to
  // retry against forever.
  const recoverFromStaleReference = async () => {
    if (!result) {
      return;
    }

    setResult(await getPhotoLookup(result.immich_asset_id));
    setStaleMessage(
      "This photo was reprocessed elsewhere since it was looked up here -- refreshed with its current data. Please try again.",
    );
  };

  const handleCorrect = async (classificationId: number, identity: string) => {
    setStaleMessage(null);

    try {
      await correctClassification(classificationId, identity);
    } catch (err) {
      if (err instanceof ClassificationNotFoundError) {
        await recoverFromStaleReference();
        return;
      }

      throw err;
    }

    setResult((current) =>
      current
        ? {
            ...current,
            detections: current.detections.map((detection) =>
              detection.classification_id === classificationId
                ? { ...detection, identity }
                : detection,
            ),
          }
        : current,
    );
  };

  const handleCorrectSpecies = async (
    classificationId: number,
    species: "dog" | "cat",
  ) => {
    setStaleMessage(null);

    try {
      await correctSpecies(classificationId, species);
    } catch (err) {
      if (err instanceof ClassificationNotFoundError) {
        await recoverFromStaleReference();
        return;
      }

      throw err;
    }

    // Species correction can reclassify the identity/confidence under the
    // new species server-side (ClassificationCorrectionService.correct_
    // species), so a full re-fetch, like the not-animal toggle above, is
    // what keeps this box's identity/confidence from going stale.
    if (result) {
      setResult(await getPhotoLookup(result.immich_asset_id));
    }
  };

  const handleToggleNotAnimal = async (cropId: number, notAnimal: boolean) => {
    setStaleMessage(null);

    try {
      if (notAnimal) {
        await markCropNotAnimal(cropId);
      } else {
        await unmarkCropNotAnimal(cropId);
      }
    } catch (err) {
      if (err instanceof CropNotFoundError) {
        await recoverFromStaleReference();
        return;
      }

      throw err;
    }

    // Marking settles the crop's classification to Unknown server-side
    // (issue #186), not just the flag -- so a full re-fetch, rather than a
    // partial patch of `not_animal` alone, is what keeps identity/
    // confidence from going stale in the UI once the mark is undone.
    if (result) {
      setResult(await getPhotoLookup(result.immich_asset_id));
    }
  };

  const handleAssign = async (
    detectionId: number,
    species: "dog" | "cat",
    identity: string | null,
  ) => {
    if (!result) {
      return;
    }

    await assignDetection(result.immich_asset_id, detectionId, species, identity);

    // The detection gains a crop/classification server-side, not just an
    // identity string -- a full re-fetch (same pattern species correction
    // and the not-animal toggle already use) is what turns this row into an
    // ordinary classified one everywhere it's rendered.
    setResult(await getPhotoLookup(result.immich_asset_id));
  };

  const handleAssignCrop = async (
    cropId: number,
    species: "dog" | "cat",
    identity: string | null,
  ) => {
    if (!result) {
      return;
    }

    await assignCrop(cropId, species, identity);

    // Same reasoning as handleAssign above: the crop gains a classification
    // server-side, so a full re-fetch turns this row into an ordinary
    // classified one everywhere it's rendered.
    setResult(await getPhotoLookup(result.immich_asset_id));
  };

  const handleRepaired = async (repairResult: AssetRepairResult) => {
    setRepairMessage(repairResult.message);
    setStaleMessage(null);
    setResult(await getPhotoLookup(repairResult.immich_asset_id));
  };

  const locationText = result ? formatLocation(result) : null;

  return (
    <section className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Look up a photo</CardTitle>
        </CardHeader>

        <CardContent className="space-y-3">
          <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
            <input
              value={urlInput}
              onChange={(event) => setUrlInput(event.target.value)}
              placeholder="Paste an Immich photo link"
              className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />

            <Button type="submit" disabled={loading || !urlInput.trim()}>
              <IconSearch className="h-4 w-4" aria-hidden="true" />
              {loading ? "Looking up…" : "Look up"}
            </Button>
          </form>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="text-sm text-muted-foreground">
              Taken {formatDate(result.captured_at)}
              {locationText && ` · ${locationText}`}
              {showAccount && result.account && ` · ${result.account}`}
            </p>

            <RepairButton
              immichAssetId={result.immich_asset_id}
              onRepaired={handleRepaired}
            />
          </div>

          {repairMessage && (
            <p className="text-sm text-muted-foreground">{repairMessage}</p>
          )}

          {staleMessage && (
            <p className="text-sm text-muted-foreground">{staleMessage}</p>
          )}

          <PhotoLookupImage
            imageUrl={`/api/photo-lookup/${encodeURIComponent(result.immich_asset_id)}/image`}
            detections={result.detections}
            hoveredDetectionId={hoveredDetectionId}
          />

          <DetectionList
            detections={result.detections}
            identities={identities}
            onCorrect={handleCorrect}
            onCorrectSpecies={handleCorrectSpecies}
            onToggleNotAnimal={handleToggleNotAnimal}
            onAssign={handleAssign}
            onAssignCrop={handleAssignCrop}
            onHoverChange={setHoveredDetectionId}
          />
        </div>
      )}
    </section>
  );
}
