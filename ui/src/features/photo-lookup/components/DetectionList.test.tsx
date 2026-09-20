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
        onAssignCrop={noop}
        onHoverChange={onHoverChange}
      />,
    );

    const row = screen.getByText("Fido (dog)").closest("div.flex.flex-wrap");
    expect(row).not.toBeNull();

    fireEvent.mouseEnter(row!);
    expect(onHoverChange).toHaveBeenLastCalledWith(2);

    fireEvent.mouseLeave(row!);
    expect(onHoverChange).toHaveBeenLastCalledWith(null);
  });

  it("labels the not-animal row's undo control 'Reclassify' and unmarks it on click (issue #267)", async () => {
    const onToggleNotAnimal = vi.fn().mockResolvedValue(undefined);

    render(
      <DetectionList
        detections={[detection({ not_animal: true, identity: null, confidence: null })]}
        identities={[]}
        onCorrect={noop}
        onCorrectSpecies={noop}
        onToggleNotAnimal={onToggleNotAnimal}
        onAssign={noop}
        onAssignCrop={noop}
        onHoverChange={() => {}}
      />,
    );

    expect(screen.getByText("Not a dog or cat")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /undo/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /reclassify/i }));

    await waitFor(() => {
      expect(onToggleNotAnimal).toHaveBeenCalledWith(1, false);
    });
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
          onAssignCrop={noop}
          onHoverChange={() => {}}
        />,
      );

      expect(screen.getByText("Sheep")).toBeInTheDocument();
      expect(screen.queryByText("Dog")).not.toBeInTheDocument();
    });

    it("renders pre-settled as not a dog or cat, with no inline species picker (issue #267)", () => {
      render(
        <DetectionList
          detections={[cropLessDetection()]}
          identities={[]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={noop}
          onAssignCrop={noop}
          onHoverChange={() => {}}
        />,
      );

      expect(screen.getByText("Not a dog or cat")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /reclassify/i })).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /not a dog or cat/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/assign identity/i)).not.toBeInTheDocument();
    });

    it("reclassifies the detection to dog, identity Unknown, on Reclassify (issue #267)", async () => {
      const onAssign = vi.fn().mockResolvedValue(undefined);

      render(
        <DetectionList
          detections={[cropLessDetection()]}
          identities={[{ id: 1, name: "Rex", species: "dog", active: true }]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={onAssign}
          onAssignCrop={noop}
          onHoverChange={() => {}}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: /reclassify/i }));

      await waitFor(() => {
        expect(onAssign).toHaveBeenCalledWith(1, "dog", null);
      });
    });
  });

  describe("a crop with no classification yet (issue #353)", () => {
    function unclassifiedDetection(
      overrides: Partial<PhotoLookupDetection> = {},
    ): PhotoLookupDetection {
      return detection({
        classification_id: null,
        identity: null,
        confidence: null,
        species: "cat",
        ...overrides,
      });
    }

    it("still offers working Dog/Cat species controls, not just a read-only badge", () => {
      render(
        <DetectionList
          detections={[unclassifiedDetection()]}
          identities={[]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={noop}
          onAssignCrop={noop}
          onHoverChange={() => {}}
        />,
      );

      expect(screen.getByRole("button", { name: /set species to dog/i })).toBeEnabled();
      expect(screen.getByRole("button", { name: /set species to cat/i })).toBeDisabled();
      expect(screen.getByText("Not classified yet")).toBeInTheDocument();
    });

    it("still offers the not-a-dog-or-cat toggle", () => {
      render(
        <DetectionList
          detections={[unclassifiedDetection()]}
          identities={[]}
          onCorrect={noop}
          onCorrectSpecies={noop}
          onToggleNotAnimal={noop}
          onAssign={noop}
          onAssignCrop={noop}
          onHoverChange={() => {}}
        />,
      );

      expect(screen.getByRole("button", { name: /not a dog or cat/i })).toBeInTheDocument();
    });

    it("assigns species via onAssignCrop rather than onCorrectSpecies, since there's no classification to correct", async () => {
      const onAssignCrop = vi.fn().mockResolvedValue(undefined);
      const onCorrectSpecies = vi.fn().mockResolvedValue(undefined);

      render(
        <DetectionList
          detections={[unclassifiedDetection({ crop_id: 7 })]}
          identities={[]}
          onCorrect={noop}
          onCorrectSpecies={onCorrectSpecies}
          onToggleNotAnimal={noop}
          onAssign={noop}
          onAssignCrop={onAssignCrop}
          onHoverChange={() => {}}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: /set species to dog/i }));

      await waitFor(() => {
        expect(onAssignCrop).toHaveBeenCalledWith(7, "dog", null);
      });

      expect(onCorrectSpecies).not.toHaveBeenCalled();
    });
  });
});
