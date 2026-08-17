import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ReviewReason } from "@/features/review/components/ReviewReason";
import { formatDate } from "@/lib/utils";
import type { Dog } from "@/types/dogs";
import type { LibraryEntry } from "@/types/library";

function speciesLabel(species: string): string {
  return species === "cat" ? "Cat" : "Dog";
}

interface Props {
  entry: LibraryEntry;
  identities: Dog[];
  onCorrect: (classificationId: number, identity: string) => Promise<void>;
}

export function LibraryEntryCard({ entry, identities, onCorrect }: Props) {
  const { item } = entry;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const speciesIdentities = identities.filter((dog) => dog.species === item.species);

  const handleChange = async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const identity = event.target.value;

    if (!identity || identity === item.prediction.identity) {
      return;
    }

    setError(null);
    setSaving(true);

    try {
      await onCorrect(item.classification_id, identity);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to correct");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="overflow-hidden">
      <img
        src={`/api/crops/${item.crop_id}`}
        alt={item.prediction.identity ?? "Unknown identity"}
        className="aspect-square w-full object-cover"
      />

      <CardContent className="space-y-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-medium">
            {item.prediction.identity ?? "Unknown"}
          </span>

          <Badge variant="outline">{speciesLabel(item.species)}</Badge>
        </div>

        {item.reason !== "review" && <ReviewReason reason={item.reason} />}

        <div className="text-sm text-muted-foreground">
          {(item.prediction.similarity * 100).toFixed(1)}% confidence
        </div>

        <div className="text-sm text-muted-foreground">
          Taken {formatDate(item.captured_at)}
        </div>

        <Badge variant={entry.reviewed ? "default" : "secondary"}>
          {entry.reviewed ? `Reviewed ${formatDate(entry.reviewed_at)}` : "Not yet reviewed"}
        </Badge>

        <select
          value={item.prediction.identity ?? ""}
          onChange={handleChange}
          disabled={saving || speciesIdentities.length === 0}
          aria-label={`Correct identity for photo ${item.crop_id}`}
          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
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

        {error && <p className="text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
