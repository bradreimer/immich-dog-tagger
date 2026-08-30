import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ReviewPage } from "./ReviewPage";
import * as api from "@/lib/api";
import type { Dog } from "@/types/dogs";
import type { ReviewItem, ReviewQueueStats } from "@/types/review";

vi.mock("@/lib/api", () => ({
  getReview: vi.fn(),
  getReviewStats: vi.fn(),
  getDogs: vi.fn(),
  getSettings: vi.fn(),
  correctClassification: vi.fn(),
  correctSpecies: vi.fn(),
  skipClassification: vi.fn(),
  markCropNotAnimal: vi.fn(),
  unmarkCropNotAnimal: vi.fn(),
  getClassification: vi.fn(),
  ClassificationNotFoundError: class ClassificationNotFoundError extends Error {},
}));

const HERMANN: Dog = { id: 1, name: "Hermann", species: "dog", active: true };

function buildItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    classification_id: 42,
    crop_id: 42,
    path: "/photos/42.jpg",
    filename: "42.jpg",
    species: "dog",
    reason: "review",
    captured_at: "2026-01-05T12:00:00Z",
    immich_asset_id: "asset-42",
    location: null,
    not_animal: false,
    prediction: {
      identity: "Hermann",
      similarity: 0.9,
      candidates: [],
    },
    suggestion: null,
    ...overrides,
  };
}

const STATS: ReviewQueueStats = { total: 1, reviewed: 0, remaining: 1 };

describe("ReviewPage", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getDogs).mockResolvedValue([HERMANN]);
    vi.mocked(api.getSettings).mockResolvedValue({
      immich_url: "http://immich.local",
      immich_external_url: "http://immich.local",
      scanned_image_count: 0,
      version: "1.11.0",
      tagging_sensitivity: "balanced",
    });
  });

  afterEach(() => {
    window.history.replaceState({}, "", originalLocation.pathname);
  });

  it("shows the active queue with its usual chrome when no classification_id is present", async () => {
    vi.mocked(api.getReview).mockResolvedValue([buildItem()]);
    vi.mocked(api.getReviewStats).mockResolvedValue(STATS);

    render(<ReviewPage />);

    expect(await screen.findByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
    expect(api.getReview).toHaveBeenCalled();
    expect(api.getClassification).not.toHaveBeenCalled();
  });

  it("loads one classification by id and hides queue chrome when classification_id is present", async () => {
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    window.history.replaceState({}, "", "/review?classification_id=42");

    render(<ReviewPage />);

    expect(await screen.findByText("Editing photo")).toBeInTheDocument();
    expect(api.getClassification).toHaveBeenCalledWith(42);
    expect(api.getReview).not.toHaveBeenCalled();

    expect(screen.queryByRole("button", { name: /skip/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "All" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to library/i })).toHaveAttribute(
      "href",
      "/library",
    );
  });

  it("corrects identity for the deep-linked photo and re-loads it", async () => {
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);
    window.history.replaceState({}, "", "/review?classification_id=42");

    render(<ReviewPage />);

    fireEvent.click(await screen.findByRole("button", { name: /hermann/i }));

    await waitFor(() =>
      expect(api.correctClassification).toHaveBeenCalledWith(42, "Hermann"),
    );
    expect(api.getClassification).toHaveBeenCalledTimes(2);
  });

  it("marks the deep-linked photo as not a dog or cat", async () => {
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    vi.mocked(api.markCropNotAnimal).mockResolvedValue(undefined);
    window.history.replaceState({}, "", "/review?classification_id=42");

    render(<ReviewPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Not a dog or cat" }));

    await waitFor(() => expect(api.markCropNotAnimal).toHaveBeenCalledWith(42));
    expect(api.getClassification).toHaveBeenCalledTimes(2);
  });

  it("shows a not-found message for a classification_id that doesn't exist", async () => {
    vi.mocked(api.getClassification).mockRejectedValue(
      new api.ClassificationNotFoundError("Classification 999 not found"),
    );
    window.history.replaceState({}, "", "/review?classification_id=999");

    render(<ReviewPage />);

    expect(await screen.findByText("Photo not found")).toBeInTheDocument();
  });
});
