import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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
        onAssign={noop}
        onMarkNotAnimal={noop}
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

  describe("a crop-less detection (issue #261)", () => {
    function cropLessDetection(
      overrides: Partial<PhotoLookupDetection> = {},
    ): PhotoLookupDetection {
      return detection({
        crop_id: null,
        classification_id: null,
        identity: null,
        confidence: null,
        species: "sheep",
        ...overrides,
      });
    }

    it("shows the raw YOLO label instead of a misleading Dog badge", () => {
      render(
        <DetectionList
          detections={[cropLessDetection()]}
          identities={[]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={noop}
          onMarkNotAnimal={noop}
          onHoverChange={() => {}}
        />,
      );

      expect(screen.getByText("Sheep")).toBeInTheDocument();
      expect(screen.queryByText("Dog")).not.toBeInTheDocument();
    });

    it("maps the detection to a chosen species and identity", async () => {
      const onAssign = vi.fn().mockResolvedValue(undefined);

      render(
        <DetectionList
          detections={[cropLessDetection()]}
          identities={[{ id: 1, name: "Rex", species: "dog", active: true }]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={onAssign}
          onMarkNotAnimal={noop}
          onHoverChange={() => {}}
        />,
      );

      fireEvent.change(screen.getByLabelText("Assign identity for detection 1"), {
        target: { value: "Rex" },
      });
      fireEvent.click(screen.getByRole("button", { name: /map to dog/i }));

      await waitFor(() => {
        expect(onAssign).toHaveBeenCalledWith(1, "dog", "Rex");
      });
    });

    it("marks the detection not a dog or cat", async () => {
      const onMarkNotAnimal = vi.fn().mockResolvedValue(undefined);

      render(
        <DetectionList
          detections={[cropLessDetection()]}
          identities={[]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={noop}
          onMarkNotAnimal={onMarkNotAnimal}
          onHoverChange={() => {}}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: /not a dog or cat/i }));

      await waitFor(() => {
        expect(onMarkNotAnimal).toHaveBeenCalledWith(1);
      });
    });
  });
});
