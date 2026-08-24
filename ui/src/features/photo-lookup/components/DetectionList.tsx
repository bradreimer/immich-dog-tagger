import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Dog } from "@/types/dogs";
import type { PhotoLookupDetection } from "@/types/photoLookup";

function speciesLabel(species: string): string {
  return species === "cat" ? "Cat" : "Dog";
}

interface RowProps {
  index: number;
  detection: PhotoLookupDetection;
  identities: Dog[];
  onCorrect: (classificationId: number, identity: string) => Promise<void>;
}

function DetectionRow({ index, detection, identities, onCorrect }: RowProps) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const speciesIdentities = identities.filter(
    (dog) => dog.species === detection.species,
  );

  const handleChange = async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const identity = event.target.value;

    if (!identity || identity === detection.identity || detection.classification_id === null) {
      return;
    }

    setError(null);
    setSaving(true);

    try {
      await onCorrect(detection.classification_id, identity);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to correct");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border py-3 last:border-b-0">
      <span className="w-6 shrink-0 text-sm font-semibold text-muted-foreground">
        {index + 1}
      </span>

      <Badge variant="outline">{speciesLabel(detection.species)}</Badge>

      <span className="min-w-0 flex-1 truncate font-medium">
        {detection.identity ?? "Unknown"}
      </span>

      {detection.confidence !== null && (
        <span className="shrink-0 text-sm text-muted-foreground">
          {(detection.confidence * 100).toFixed(1)}% confidence
        </span>
      )}

      {detection.classification_id !== null ? (
        <select
          value={detection.identity ?? ""}
          onChange={handleChange}
          disabled={saving || speciesIdentities.length === 0}
          aria-label={`Correct identity for detection ${index + 1}`}
          className="h-9 shrink-0 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="" disabled>
            {speciesIdentities.length === 0 ? "No identities configured" : "Correct to…"}
          </option>
          {speciesIdentities.map((dog) => (
            <option key={dog.id} value={dog.name}>
              {dog.name}
            </option>
          ))}
        </select>
      ) : (
        <span className="shrink-0 text-sm text-muted-foreground">
          Not classified yet
        </span>
      )}

      {error && <p className="w-full text-xs text-destructive">{error}</p>}
    </div>
  );
}

interface Props {
  detections: PhotoLookupDetection[];
  identities: Dog[];
  onCorrect: (classificationId: number, identity: string) => Promise<void>;
}

export function DetectionList({ detections, identities, onCorrect }: Props) {
  if (detections.length === 0) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-muted-foreground">
          No dogs or cats were detected in this photo.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        {detections.map((detection, index) => (
          <DetectionRow
            key={detection.detection_id}
            index={index}
            detection={detection}
            identities={identities}
            onCorrect={onCorrect}
          />
        ))}
      </CardContent>
    </Card>
  );
}
