import { describe, expect, it } from "vitest";

import { immichAssetUrl } from "./immich";

describe("immichAssetUrl", () => {
  it("builds a photo deep link from the configured base URL", () => {
    expect(immichAssetUrl("http://immich.local:2283", "asset-42")).toBe(
      "http://immich.local:2283/photos/asset-42",
    );
  });

  it("tolerates a trailing slash on the configured base URL", () => {
    expect(immichAssetUrl("http://immich.local:2283///", "asset-42")).toBe(
      "http://immich.local:2283/photos/asset-42",
    );
  });

  it("returns null when the base URL is not configured", () => {
    expect(immichAssetUrl("", "asset-42")).toBeNull();
    expect(immichAssetUrl(null, "asset-42")).toBeNull();
  });

  it("returns null when the asset id is unknown", () => {
    expect(immichAssetUrl("http://immich.local:2283", null)).toBeNull();
  });
});
