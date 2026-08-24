import { describe, expect, it } from "vitest";

import { immichAssetUrl, parseImmichAssetId } from "./immich";

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

describe("parseImmichAssetId", () => {
  it("extracts the asset id from a photo URL", () => {
    expect(
      parseImmichAssetId("http://immich.local:2283/photos/asset-42"),
    ).toBe("asset-42");
  });

  it("tolerates a trailing slash", () => {
    expect(
      parseImmichAssetId("http://immich.local:2283/photos/asset-42/"),
    ).toBe("asset-42");
  });

  it("tolerates surrounding whitespace", () => {
    expect(
      parseImmichAssetId("  http://immich.local:2283/photos/asset-42  "),
    ).toBe("asset-42");
  });

  it("decodes a URL-encoded asset id", () => {
    expect(
      parseImmichAssetId("http://immich.local:2283/photos/a%20b"),
    ).toBe("a b");
  });

  it("ignores query strings and fragments after the asset id", () => {
    expect(
      parseImmichAssetId(
        "http://immich.local:2283/photos/asset-42?album=abc#top",
      ),
    ).toBe("asset-42");
  });

  it("returns null for a URL that isn't a photo link", () => {
    expect(
      parseImmichAssetId("http://immich.local:2283/albums/asset-42"),
    ).toBeNull();
  });

  it("returns null for an empty or unparseable string", () => {
    expect(parseImmichAssetId("")).toBeNull();
    expect(parseImmichAssetId("   ")).toBeNull();
    expect(parseImmichAssetId("not a url")).toBeNull();
  });
});
