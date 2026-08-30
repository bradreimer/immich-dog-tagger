import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { LibraryEntry } from "@/types/library";

interface Props {
  entry: LibraryEntry;
  selected: boolean;
  onSelect: () => void;
}

export function LibraryThumbnail({ entry, selected, onSelect }: Props) {
  const { item } = entry;
  const name = item.not_animal ? "Not a dog or cat" : (item.prediction.identity ?? "Unknown");

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`View details for ${name}`}
      className={cn(
        "overflow-hidden rounded-lg border text-left transition-colors",
        selected ? "border-primary ring-2 ring-primary" : "border-border",
      )}
    >
      <img
        src={`/api/crops/${item.crop_id}`}
        alt={name}
        loading="lazy"
        decoding="async"
        className="aspect-square w-full object-cover"
      />

      <div className="space-y-1 p-2">
        <span className="block truncate text-sm font-medium">{name}</span>

        <Badge variant={entry.reviewed ? "default" : "secondary"} className="text-xs">
          {entry.reviewed ? "Reviewed" : "Unreviewed"}
        </Badge>
      </div>
    </button>
  );
}
