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
  repairAsset: vi.fn(),
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

    render(<ReviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
    expect(api.getReview).toHaveBeenCalled();
    expect(api.getClassification).not.toHaveBeenCalled();
  });

  it("combines a Library filter bridge from the URL with the reason-based filter", async () => {
    vi.mocked(api.getReview).mockResolvedValue([buildItem()]);
    vi.mocked(api.getReviewStats).mockResolvedValue(STATS);
    window.history.replaceState(
      {},
      "",
      "/review?species=dog&identity=Hermann&captured_after=2026-01-01",
    );

    render(<ReviewPage onNavigate={vi.fn()} />);

    await waitFor(() =>
      expect(api.getReview).toHaveBeenCalledWith(
        expect.objectContaining({
          species: "dog",
          identity: "Hermann",
          captured_after: "2026-01-01",
        }),
      ),
    );

    expect(await screen.findByText(/Filtered from Library: dog, Hermann, after 2026-01-01/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Unknown" }));

    await waitFor(() =>
      expect(api.getReview).toHaveBeenLastCalledWith(
        expect.objectContaining({
          unknown: true,
          species: "dog",
          identity: "Hermann",
          captured_after: "2026-01-01",
        }),
      ),
    );
  });

  it("loads one classification by id and hides queue chrome when classification_id is present", async () => {
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    window.history.replaceState({}, "", "/review?classification_id=42");

    render(<ReviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("Editing photo")).toBeInTheDocument();
    expect(api.getClassification).toHaveBeenCalledWith(42);
    expect(api.getReview).not.toHaveBeenCalled();

    expect(screen.queryByRole("button", { name: /skip/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "All" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to library/i })).toBeInTheDocument();
  });

  it("corrects identity for the deep-linked photo and re-loads it", async () => {
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);
    window.history.replaceState({}, "", "/review?classification_id=42");

    render(<ReviewPage onNavigate={vi.fn()} />);

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

    render(<ReviewPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Not a dog or cat" }));

    await waitFor(() => expect(api.markCropNotAnimal).toHaveBeenCalledWith(42));
    expect(api.getClassification).toHaveBeenCalledTimes(2);
  });

  it("shows a not-found message for a classification_id that doesn't exist", async () => {
    vi.mocked(api.getClassification).mockRejectedValue(
      new api.ClassificationNotFoundError("Classification 999 not found"),
    );
    window.history.replaceState({}, "", "/review?classification_id=999");

    render(<ReviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("Photo not found")).toBeInTheDocument();
  });

  it("navigates via onNavigate, not a real anchor, for all three Back to Library affordances", async () => {
    window.history.replaceState({}, "", "/review?classification_id=42");

    // Normal editing view.
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    const onNavigateNormal = vi.fn();
    const { unmount: unmountNormal } = render(<ReviewPage onNavigate={onNavigateNormal} />);
    const normalBackLink = await screen.findByRole("button", { name: /back to library/i });
    expect(normalBackLink.tagName).toBe("BUTTON");
    fireEvent.click(normalBackLink);
    expect(onNavigateNormal).toHaveBeenCalledWith("/library");
    unmountNormal();

    // "Photo not found" state.
    vi.mocked(api.getClassification).mockRejectedValue(
      new api.ClassificationNotFoundError("Classification 42 not found"),
    );
    const onNavigateNotFound = vi.fn();
    const { unmount: unmountNotFound } = render(<ReviewPage onNavigate={onNavigateNotFound} />);
    const notFoundBackLink = await screen.findByRole("button", { name: /back to library/i });
    expect(notFoundBackLink.tagName).toBe("BUTTON");
    fireEvent.click(notFoundBackLink);
    expect(onNavigateNotFound).toHaveBeenCalledWith("/library");
    unmountNotFound();

    // "Photo repaired" state, reached by confirming Repair on the normal view.
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    vi.mocked(api.repairAsset).mockResolvedValue({
      asset_id: 1,
      immich_asset_id: "asset-42",
      status: "ok",
      detections: 1,
      dogs: 1,
      cats: 0,
      classified: 1,
      message: "Repaired.",
    });
    const onNavigateRepaired = vi.fn();
    render(<ReviewPage onNavigate={onNavigateRepaired} />);
    await screen.findByRole("button", { name: /back to library/i });
    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    fireEvent.click(await screen.findByRole("button", { name: "Yes, repair" }));
    await screen.findByText("Photo repaired");
    const repairedBackLink = screen.getByRole("button", { name: /back to library/i });
    expect(repairedBackLink.tagName).toBe("BUTTON");
    fireEvent.click(repairedBackLink);
    expect(onNavigateRepaired).toHaveBeenCalledWith("/library");
  });

  it("celebrates when a review action crosses a multiple of 10 reviewed", async () => {
    vi.mocked(api.getReview).mockResolvedValue([buildItem()]);
    vi.mocked(api.getReviewStats)
      .mockResolvedValueOnce({ total: 20, reviewed: 9, remaining: 11 })
      .mockResolvedValueOnce({ total: 20, reviewed: 10, remaining: 10 });
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);

    render(<ReviewPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /hermann/i }));

    expect(await screen.findByText(/10 reviewed/i)).toBeInTheDocument();
  });

  it("does not celebrate on the initial load, only after an action reaches a milestone", async () => {
    vi.mocked(api.getReview).mockResolvedValue([buildItem()]);
    vi.mocked(api.getReviewStats).mockResolvedValue({
      total: 20,
      reviewed: 10,
      remaining: 10,
    });

    render(<ReviewPage onNavigate={vi.fn()} />);

    await screen.findByRole("button", { name: /hermann/i });

    expect(screen.queryByText(/10 reviewed/i)).not.toBeInTheDocument();
  });

  it("does not celebrate when the reviewed count doesn't land on a multiple of 10", async () => {
    vi.mocked(api.getReview).mockResolvedValue([buildItem()]);
    vi.mocked(api.getReviewStats)
      .mockResolvedValueOnce({ total: 20, reviewed: 10, remaining: 10 })
      .mockResolvedValueOnce({ total: 20, reviewed: 11, remaining: 9 });
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);

    render(<ReviewPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /hermann/i }));

    await waitFor(() => expect(api.correctClassification).toHaveBeenCalled());
    expect(screen.queryByText(/reviewed — nice streak/i)).not.toBeInTheDocument();
  });

  it("never shows the milestone celebration on the single-item edit view", async () => {
    vi.mocked(api.getClassification).mockResolvedValue(buildItem());
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);
    window.history.replaceState({}, "", "/review?classification_id=42");

    render(<ReviewPage onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /hermann/i }));

    await waitFor(() =>
      expect(api.correctClassification).toHaveBeenCalledWith(42, "Hermann"),
    );
    expect(api.getReviewStats).not.toHaveBeenCalled();
    expect(screen.queryByText(/reviewed — nice streak/i)).not.toBeInTheDocument();
  });
});
