import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

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
    immich_asset_id: "asset-42",
    location: null,
    not_animal: false,
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
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("Unknown identity")).toBeInTheDocument();
    expect(screen.getByText("January 5, 2026")).toBeInTheDocument();
  });

  it("links to the original photo in Immich beside the reason and date", () => {
    render(
      <ReviewCard
        item={buildItem()}
        identities={["Rex"]}
        immichUrl="http://immich.local:2283/"
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    const link = screen.getByRole("link", { name: /view in immich/i });

    expect(link).toHaveAttribute(
      "href",
      "http://immich.local:2283/photos/asset-42",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("omits the Immich link when no Immich URL is configured", () => {
    render(
      <ReviewCard
        item={buildItem()}
        identities={["Rex"]}
        immichUrl={null}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("Unknown identity")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /view in immich/i }),
    ).not.toBeInTheDocument();
  });

  it("omits the Immich link when the item has no Immich asset", () => {
    render(
      <ReviewCard
        item={buildItem({ immich_asset_id: null })}
        identities={["Rex"]}
        immichUrl="http://immich.local:2283"
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    expect(
      screen.queryByRole("link", { name: /view in immich/i }),
    ).not.toBeInTheDocument();
  });

  it("links to the Photo Lookup view for the same photo", () => {
    render(
      <ReviewCard
        item={buildItem()}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    const link = screen.getByRole("link", { name: /view in photo lookup/i });

    expect(link).toHaveAttribute("href", "/photo-lookup?assetId=asset-42");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("omits the Photo Lookup link when the item has no Immich asset", () => {
    render(
      <ReviewCard
        item={buildItem({ immich_asset_id: null })}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    expect(
      screen.queryByRole("link", { name: /view in photo lookup/i }),
    ).not.toBeInTheDocument();
  });

  it("marks a photo as not a dog or cat", () => {
    const onToggleNotAnimal = vi.fn();

    render(
      <ReviewCard
        item={buildItem()}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={onToggleNotAnimal}
        disabled={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Not a dog or cat" }));

    expect(onToggleNotAnimal).toHaveBeenCalled();
  });

  it("offers to undo an existing not-a-dog-or-cat mark", () => {
    render(
      <ReviewCard
        item={buildItem({ not_animal: true })}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Undo — this is a dog or cat" }),
    ).toBeInTheDocument();
  });

  it("falls back to a placeholder when the capture date is unknown", () => {
    render(
      <ReviewCard
        item={buildItem({ captured_at: null })}
        identities={["Rex"]}
        onCorrect={vi.fn()}
        onCorrectSpecies={vi.fn()}
        onSkip={vi.fn()}
        onToggleNotAnimal={vi.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("Date unknown")).toBeInTheDocument();
  });
});
