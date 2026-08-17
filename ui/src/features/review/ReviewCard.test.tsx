import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ReviewCard } from "./ReviewCard";
import type { ReviewItem } from "../../types/review";

function buildItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    classification_id: 1,
    crop_id: 1,
    path: "/photos/x.jpg",
    filename: "x.jpg",
    species: "dog",
    reason: "unknown",
    captured_at: "2026-01-05T12:00:00Z",
    prediction: {
      identity: null,
      similarity: 0.4,
      candidates: [],
    },
    suggestion: null,
    ...overrides,
  };
}

describe("ReviewCard", () => {
  it("shows the capture date beside the review reason badge, below the image", () => {
    render(
      <ReviewCard
        item={buildItem()}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("Unknown identity")).toBeInTheDocument();
    expect(screen.getByText("January 5, 2026")).toBeInTheDocument();
  });

  it("falls back to a placeholder when the capture date is unknown", () => {
    render(
      <ReviewCard
        item={buildItem({ captured_at: null })}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("Date unknown")).toBeInTheDocument();
  });
});
