import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ImmichPhotoLink } from "@/features/review/components/ImmichPhotoLink";
import { PhotoLookupLink } from "@/features/review/components/PhotoLookupLink";
import { formatDate } from "@/lib/utils";
import type { LibraryEntry } from "@/types/library";

function speciesLabel(species: string): string {
  return species === "cat" ? "Cat" : "Dog";
}

interface Props {
  entry: LibraryEntry;
  immichUrl: string | null;
}

export function LibraryDetailsPanel({ entry, immichUrl }: Props) {
  const { item } = entry;
  const name = item.not_animal ? "Not a dog or cat" : (item.prediction.identity ?? "Unknown");

  return (
    <Card className="h-fit lg:sticky lg:top-6">
      <CardHeader>
        <CardTitle>{name}</CardTitle>
      </CardHeader>

      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
          <span className="text-muted-foreground">Species</span>
          <span>{speciesLabel(item.species)}</span>

          <span className="text-muted-foreground">Confidence</span>
          <span>{(item.prediction.similarity * 100).toFixed(1)}%</span>

          <span className="text-muted-foreground">Captured</span>
          <span>{formatDate(item.captured_at)}</span>

          <span className="text-muted-foreground">Location</span>
          <span>{item.location ?? "Unknown"}</span>

          <span className="text-muted-foreground">Review status</span>
          <span>
            <Badge variant={entry.reviewed ? "default" : "secondary"}>
              {entry.reviewed ? `Reviewed ${formatDate(entry.reviewed_at)}` : "Not yet reviewed"}
            </Badge>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border pt-3">
          <ImmichPhotoLink immichUrl={immichUrl} assetId={item.immich_asset_id} />
          <PhotoLookupLink assetId={item.immich_asset_id} />
        </div>
      </CardContent>
    </Card>
  );
}
