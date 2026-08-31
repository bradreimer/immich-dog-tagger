import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { LibraryDetailsPanel } from "./LibraryDetailsPanel";
import type { LibraryEntry } from "@/types/library";

const ENTRY: LibraryEntry = {
  reviewed: false,
  reviewed_at: null,
  item: {
    classification_id: 1,
    crop_id: 1,
    path: "/photos/1.jpg",
    filename: "1.jpg",
    species: "dog",
    reason: "review",
    captured_at: "2026-01-05T12:00:00Z",
    immich_asset_id: "asset-1",
    location: "Portland, Oregon, USA",
    not_animal: false,
    prediction: {
      identity: "Hermann",
      similarity: 0.9,
      candidates: [],
    },
    suggestion: null,
  },
};

describe("LibraryDetailsPanel", () => {
  it("stays clamped to the top of the window while the page scrolls (lg and up)", () => {
    const { container } = render(<LibraryDetailsPanel entry={ENTRY} immichUrl={null} />);

    const card = container.querySelector('[data-slot="card"]');

    // `lg:sticky` tracks scroll instead of scrolling away with the grid;
    // `lg:top-6` clamps its top edge to a small fixed offset from the top
    // of the window rather than letting it scroll above the viewport.
    // No bottom clamp is required -- it may scroll out of view once the
    // grid content above it ends.
    expect(card).toHaveClass("lg:sticky", "lg:top-6");
  });
});
