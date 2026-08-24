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

/**
 * The reverse of immichAssetUrl(): pulls the asset id back out of a pasted
 * Immich photo URL (`{base}/photos/{assetId}`, any host). Returns null for
 * anything that isn't that shape, so callers can reject it as unparseable
 * up front rather than looking up garbage (issue #179).
 */
export function parseImmichAssetId(url: string): string | null {
  const trimmed = url.trim();

  if (!trimmed) {
    return null;
  }

  let parsed: URL;

  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }

  const match = parsed.pathname.match(/\/photos\/([^/?#]+)\/?$/);

  return match ? decodeURIComponent(match[1]) : null;
}
