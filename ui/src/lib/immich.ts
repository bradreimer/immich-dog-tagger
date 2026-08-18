/**
 * Deep link to an asset in the user's own Immich instance, built client-side
 * from the configured base URL (`IMMICH_URL`, surfaced via `GET /api/settings`).
 *
 * Returns null when either half is missing, so callers can omit the link
 * rather than render a broken one.
 */
export function immichAssetUrl(
  baseUrl: string | null | undefined,
  assetId: string | null | undefined,
): string | null {
  if (!baseUrl || !assetId) {
    return null;
  }

  return `${baseUrl.replace(/\/+$/, "")}/photos/${assetId}`;
}
