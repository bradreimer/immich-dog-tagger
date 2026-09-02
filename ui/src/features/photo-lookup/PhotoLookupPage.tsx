import { useEffect, useState } from "react";

import { IconSearch } from "@tabler/icons-react";

import {
  PhotoLookupNotFoundError,
  correctClassification,
  correctSpecies,
  getDogs,
  getPhotoLookup,
  markCropNotAnimal,
  unmarkCropNotAnimal,
} from "@/lib/api";
import { parseImmichAssetId } from "@/lib/immich";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { Dog } from "@/types/dogs";
import type { PhotoLookupResult } from "@/types/photoLookup";

import { DetectionList } from "./components/DetectionList";
import { PhotoLookupImage } from "./components/PhotoLookupImage";

export function PhotoLookupPage() {
  const [urlInput, setUrlInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PhotoLookupResult | null>(null);
  const [identities, setIdentities] = useState<Dog[]>([]);

  useEffect(() => {
    getDogs()
      .then(setIdentities)
      .catch(() => setIdentities([]));
  }, []);

  const runLookup = async (assetId: string) => {
    setError(null);
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

  const handleCorrect = async (classificationId: number, identity: string) => {
    await correctClassification(classificationId, identity);

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
    await correctSpecies(classificationId, species);

    // Species correction can reclassify the identity/confidence under the
    // new species server-side (ClassificationCorrectionService.correct_
    // species), so a full re-fetch, like the not-animal toggle above, is
    // what keeps this box's identity/confidence from going stale.
    if (result) {
      setResult(await getPhotoLookup(result.immich_asset_id));
    }
  };

  const handleToggleNotAnimal = async (cropId: number, notAnimal: boolean) => {
    if (notAnimal) {
      await markCropNotAnimal(cropId);
    } else {
      await unmarkCropNotAnimal(cropId);
    }

    // Marking settles the crop's classification to Unknown server-side
    // (issue #186), not just the flag -- so a full re-fetch, rather than a
    // partial patch of `not_animal` alone, is what keeps identity/
    // confidence from going stale in the UI once the mark is undone.
    if (result) {
      setResult(await getPhotoLookup(result.immich_asset_id));
    }
  };

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
          <p className="text-sm text-muted-foreground">
            Taken {formatDate(result.captured_at)}
          </p>

          <PhotoLookupImage
            imageUrl={`/api/photo-lookup/${encodeURIComponent(result.immich_asset_id)}/image`}
            detections={result.detections}
          />

          <DetectionList
            detections={result.detections}
            identities={identities}
            onCorrect={handleCorrect}
            onCorrectSpecies={handleCorrectSpecies}
            onToggleNotAnimal={handleToggleNotAnimal}
          />
        </div>
      )}
    </section>
  );
}
