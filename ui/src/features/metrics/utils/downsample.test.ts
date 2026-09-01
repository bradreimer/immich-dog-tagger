import { describe, expect, it } from "vitest";

import { downsampleForDisplay } from "./downsample";

describe("downsampleForDisplay", () => {
  it("passes small inputs through unchanged", () => {
    const points = [1, 2, 3, 4, 5];

    expect(downsampleForDisplay(points, 10)).toEqual(points);
  });

  it("returns input unchanged when length equals the cap", () => {
    const points = [1, 2, 3];

    expect(downsampleForDisplay(points, 3)).toEqual(points);
  });

  it("caps the output length and always keeps the first and last point", () => {
    const points = Array.from({ length: 100 }, (_, i) => i);

    const result = downsampleForDisplay(points, 10);

    expect(result.length).toBeLessThanOrEqual(10);
    expect(result[0]).toBe(0);
    expect(result[result.length - 1]).toBe(99);
  });

  it("keeps points in their original order", () => {
    const points = Array.from({ length: 50 }, (_, i) => i);

    const result = downsampleForDisplay(points, 12);

    for (let i = 1; i < result.length; i++) {
      expect(result[i]).toBeGreaterThan(result[i - 1]);
    }
  });

  it("never returns fewer than 2 points when given at least 2", () => {
    const points = [1, 2];

    expect(downsampleForDisplay(points, 1)).toEqual([1, 2]);
  });

  it("passes a single point through unchanged", () => {
    expect(downsampleForDisplay([42], 10)).toEqual([42]);
  });
});
