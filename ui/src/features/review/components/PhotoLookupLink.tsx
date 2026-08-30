import { IconSearch } from "@tabler/icons-react";

interface Props {
  assetId: string | null;
}

/**
 * Opens the Photo Lookup view for this photo, showing a box over every
 * detected dog/cat in it rather than just the crop under review. Renders
 * nothing unless the asset id is known.
 */
export function PhotoLookupLink({ assetId }: Props) {
  if (!assetId) {
    return null;
  }

  return (
    <a
      href={`/photo-lookup?assetId=${encodeURIComponent(assetId)}`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
    >
      <IconSearch className="h-4 w-4" aria-hidden="true" />
      View in Photo Lookup
    </a>
  );
}
