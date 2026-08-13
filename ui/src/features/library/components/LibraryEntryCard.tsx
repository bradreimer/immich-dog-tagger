import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { LibraryEntry } from "@/types/library";

function formatDate(value: string | null): string {
  if (!value) {
    return "Date unknown";
  }

  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function speciesLabel(species: string): string {
  return species === "cat" ? "Cat" : "Dog";
}

interface Props {
  entry: LibraryEntry;
}

export function LibraryEntryCard({ entry }: Props) {
  const { item } = entry;

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

        <div className="text-sm text-muted-foreground">
          {(item.prediction.similarity * 100).toFixed(1)}% confidence
        </div>

        <div className="text-sm text-muted-foreground">
          Taken {formatDate(item.captured_at)}
        </div>

        <Badge variant={entry.reviewed ? "default" : "secondary"}>
          {entry.reviewed ? `Reviewed ${formatDate(entry.reviewed_at)}` : "Not yet reviewed"}
        </Badge>
      </CardContent>
    </Card>
  );
}
