import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { PhotoLookupDetection } from "@/types/photoLookup";

import { PhotoLookupImage } from "./PhotoLookupImage";

function detection(overrides: Partial<PhotoLookupDetection> = {}): PhotoLookupDetection {
  return {
    detection_id: 1,
    x1: 10,
    y1: 10,
    x2: 50,
    y2: 50,
    species: "dog",
    crop_id: 1,
    classification_id: 1,
    identity: "Rex",
    confidence: 0.9,
    not_animal: false,
    ...overrides,
  };
}

// jsdom never actually decodes the image, so naturalWidth/naturalHeight stay
// 0 until the load handler reads them off the <img> element -- this mimics
// what the browser reports once the photo has actually loaded.
function loadImage(width: number, height: number) {
  const img = screen.getByRole("img");
  Object.defineProperty(img, "naturalWidth", { value: width, configurable: true });
  Object.defineProperty(img, "naturalHeight", { value: height, configurable: true });
  fireEvent.load(img);
}

describe("PhotoLookupImage", () => {
  it("positions a box that fits within the image's natural size", () => {
    render(
      <PhotoLookupImage
        imageUrl="/api/photo-lookup/asset-1/image"
        detections={[detection()]}
      />,
    );

    loadImage(200, 100);

    expect(screen.getByText("1. Rex")).toBeInTheDocument();
    expect(screen.queryByText(/coordinates fall outside/i)).not.toBeInTheDocument();
  });

  it("flags a detection whose box falls outside the displayed image instead of drawing it", () => {
    // Issue #220: a detection computed before the EXIF-orientation fix is
    // stored in the old, rotated coordinate space -- against today's
    // correctly-oriented image, its box lands outside the frame.
    render(
      <PhotoLookupImage
        imageUrl="/api/photo-lookup/asset-1/image"
        detections={[detection({ x2: 250 })]}
      />,
    );

    loadImage(200, 100);

    expect(screen.queryByText("1. Rex")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Box not shown for detection 1: coordinates fall outside this image, which usually means it predates an orientation fix and needs reprocessing.",
      ),
    ).toBeInTheDocument();
  });

  it("pluralizes the warning and reports every affected detection's number", () => {
    render(
      <PhotoLookupImage
        imageUrl="/api/photo-lookup/asset-1/image"
        detections={[
          detection({ detection_id: 1, identity: "Rex" }),
          detection({ detection_id: 2, identity: "Fido", x2: 250 }),
          detection({ detection_id: 3, identity: "Spot", y2: 150 }),
        ]}
      />,
    );

    loadImage(200, 100);

    expect(screen.getByText("1. Rex")).toBeInTheDocument();
    expect(screen.queryByText("2. Fido")).not.toBeInTheDocument();
    expect(screen.queryByText("3. Spot")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Boxes not shown for detections 2, 3: coordinates fall outside this image, which usually means they predate an orientation fix and need reprocessing.",
      ),
    ).toBeInTheDocument();
  });

  it("does not flag anything before the image has finished loading", () => {
    render(
      <PhotoLookupImage
        imageUrl="/api/photo-lookup/asset-1/image"
        detections={[detection({ x2: 250 })]}
      />,
    );

    expect(screen.queryByText(/coordinates fall outside/i)).not.toBeInTheDocument();
  });
});
