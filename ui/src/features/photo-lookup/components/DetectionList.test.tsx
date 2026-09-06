import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { PhotoLookupDetection } from "@/types/photoLookup";

import { DetectionList } from "./DetectionList";

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

function noop() {
  return Promise.resolve();
}

describe("DetectionList", () => {
  it("reports the detection id on hover and null on unhover", () => {
    const onHoverChange = vi.fn();

    render(
      <DetectionList
        detections={[
          detection({ detection_id: 1, identity: "Rex" }),
          detection({ detection_id: 2, identity: "Fido" }),
        ]}
        identities={[]}
        onCorrect={noop}
        onCorrectSpecies={noop}
        onToggleNotAnimal={noop}
        onClassifyPending={noop}
        onHoverChange={onHoverChange}
      />,
    );

    const row = screen.getByText("Fido").closest("div.flex.flex-wrap");
    expect(row).not.toBeNull();

    fireEvent.mouseEnter(row!);
    expect(onHoverChange).toHaveBeenLastCalledWith(2);

    fireEvent.mouseLeave(row!);
    expect(onHoverChange).toHaveBeenLastCalledWith(null);
  });
});
