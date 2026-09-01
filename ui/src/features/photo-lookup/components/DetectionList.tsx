import { useState } from "react";

import { IconCat, IconDog, IconX } from "@tabler/icons-react";

import { SPECIES_STYLES } from "@/features/review/utils/speciesStyles";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
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
  onCorrectSpecies: (classificationId: number, species: "dog" | "cat") => Promise<void>;
  onToggleNotAnimal: (cropId: number, notAnimal: boolean) => Promise<void>;
}

function DetectionRow({
  index,
  detection,
  identities,
  onCorrect,
  onCorrectSpecies,
  onToggleNotAnimal,
}: RowProps) {
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

  const handleCorrectSpecies = async (species: "dog" | "cat") => {
    if (species === detection.species || detection.classification_id === null) {
      return;
    }

    setError(null);
    setSaving(true);

    try {
      await onCorrectSpecies(detection.classification_id, species);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to correct species");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleNotAnimal = async () => {
    if (detection.crop_id === null) {
      return;
    }

    setError(null);
    setSaving(true);

    try {
      await onToggleNotAnimal(detection.crop_id, !detection.not_animal);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border py-3 last:border-b-0">
      <span className="w-6 shrink-0 text-sm font-semibold text-muted-foreground">
        {index + 1}
      </span>

      {detection.not_animal || detection.classification_id === null ? (
        <Badge variant="outline">{speciesLabel(detection.species)}</Badge>
      ) : (
        <div
          className="flex shrink-0 gap-1"
          role="group"
          aria-label={`Correct species for detection ${index + 1}`}
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn(SPECIES_STYLES.dog)}
            aria-pressed={detection.species === "dog"}
            aria-label="Set species to Dog"
            disabled={saving || detection.species === "dog"}
            onClick={() => handleCorrectSpecies("dog")}
          >
            <IconDog className="h-4 w-4" aria-hidden="true" />
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn(SPECIES_STYLES.cat)}
            aria-pressed={detection.species === "cat"}
            aria-label="Set species to Cat"
            disabled={saving || detection.species === "cat"}
            onClick={() => handleCorrectSpecies("cat")}
          >
            <IconCat className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      )}

      {detection.not_animal ? (
        <span className="min-w-0 flex-1 truncate font-medium text-muted-foreground">
          Not a dog or cat
        </span>
      ) : (
        <>
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
        </>
      )}

      {detection.crop_id !== null && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleToggleNotAnimal}
          disabled={saving}
          className="shrink-0"
        >
          {!detection.not_animal && <IconX className="h-4 w-4" aria-hidden="true" />}
          {detection.not_animal ? "Undo" : "Not a dog or cat"}
        </Button>
      )}

      {error && <p className="w-full text-xs text-destructive">{error}</p>}
    </div>
  );
}

interface Props {
  detections: PhotoLookupDetection[];
  identities: Dog[];
  onCorrect: (classificationId: number, identity: string) => Promise<void>;
  onCorrectSpecies: (classificationId: number, species: "dog" | "cat") => Promise<void>;
  onToggleNotAnimal: (cropId: number, notAnimal: boolean) => Promise<void>;
}

export function DetectionList({
  detections,
  identities,
  onCorrect,
  onCorrectSpecies,
  onToggleNotAnimal,
}: Props) {
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
            onCorrectSpecies={onCorrectSpecies}
            onCorrect={onCorrect}
            onToggleNotAnimal={onToggleNotAnimal}
          />
        ))}
      </CardContent>
    </Card>
  );
}
