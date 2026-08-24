import { useEffect, useState } from "react";

import { IconSearch } from "@tabler/icons-react";

import {
  PhotoLookupNotFoundError,
  correctClassification,
  getDogs,
  getPhotoLookup,
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
          />
        </div>
      )}
    </section>
  );
}
