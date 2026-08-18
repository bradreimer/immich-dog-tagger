import { IconExternalLink } from "@tabler/icons-react";

import { immichAssetUrl } from "@/lib/immich";

interface Props {
  immichUrl: string | null;
  assetId: string | null;
}

/**
 * Opens the original, uncropped photo in Immich when the crop alone isn't
 * enough to identify the dog. Renders nothing unless both the configured
 * Immich URL and the asset id are known.
 */
export function ImmichPhotoLink({ immichUrl, assetId }: Props) {
  const href = immichAssetUrl(immichUrl, assetId);

  if (!href) {
    return null;
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
    >
      <IconExternalLink className="h-4 w-4" aria-hidden="true" />
      View in Immich
    </a>
  );
}
