import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ReviewGroupedPanel } from "./ReviewGroupedPanel";
import * as api from "../../../lib/api";
import type { ReviewGroup } from "../../../types/clusters";
import type { ReviewItem } from "../../../types/review";
import type { Dog } from "../../../types/dogs";

vi.mock("../../../lib/api", () => ({
  getReviewGroups: vi.fn(),
  approveCluster: vi.fn(),
  reassignCluster: vi.fn(),
  rejectCluster: vi.fn(),
  correctClassification: vi.fn(),
  correctSpecies: vi.fn(),
  skipClassification: vi.fn(),
  markCropNotAnimal: vi.fn(),
  unmarkCropNotAnimal: vi.fn(),
}));

const REX: Dog = { id: 1, name: "Rex", species: "dog", active: true };

function buildItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    classification_id: overrides.classification_id ?? 1,
    crop_id: overrides.crop_id ?? 1,
    path: "/photos/x.jpg",
    filename: "x.jpg",
    species: "dog",
    reason: "review",
    captured_at: "2026-01-05T12:00:00Z",
    immich_asset_id: "asset-1",
    location: null,
    not_animal: false,
    prediction: {
      identity: "Rex",
      similarity: 0.8,
      candidates: [],
    },
    suggestion: null,
    ...overrides,
  };
}

function buildGroup(overrides: Partial<ReviewGroup> = {}): ReviewGroup {
  const members = [
    buildItem({ classification_id: 1, crop_id: 1 }),
    buildItem({ classification_id: 2, crop_id: 2 }),
  ];

  return {
    identity: "Rex",
    species: "dog",
    cluster: {
      id: 1,
      size: members.length,
      representative: members[0],
      members,
      min_similarity: 0.7,
      max_similarity: 0.9,
      earliest_captured_at: null,
      latest_captured_at: null,
    },
    ...overrides,
  };
}

describe("ReviewGroupedPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads and renders a batch, showing its identity and size", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    expect(await screen.findByText("Rex")).toBeInTheDocument();
    expect(screen.getByText("2 photos")).toBeInTheDocument();
  });

  it("shows an empty state when there are no batches", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [],
      identity_count: 0,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    expect(await screen.findByText(/no batches of similar photos/i)).toBeInTheDocument();
  });

  it("approves the whole (fully selected) group and refreshes stats", async () => {
    const group = buildGroup();
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.approveCluster).mockResolvedValue({
      identity: "Rex",
      applied: 2,
      skipped: 0,
      skips: [],
    });

    const onReviewed = vi.fn();

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={onReviewed} />);

    const approveButton = await screen.findByRole("button", { name: /approve 2 as rex/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(api.approveCluster).toHaveBeenCalledWith("Rex", "dog", [1, 2]);
    });

    expect(onReviewed).toHaveBeenCalled();
    expect(await screen.findByText(/approved 2 as rex/i)).toBeInTheDocument();
  });

  it("approves the group as an alternate top-predicted identity", async () => {
    const group = buildGroup({
      cluster: {
        ...buildGroup().cluster,
        representative: buildItem({
          classification_id: 1,
          crop_id: 1,
          prediction: {
            identity: "Rex",
            similarity: 0.8,
            candidates: [
              { identity: "Rex", similarity: 0.8, matched_example_id: 1 },
              { identity: "Fido", similarity: 0.62, matched_example_id: 2 },
            ],
          },
        }),
      },
    });
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.reassignCluster).mockResolvedValue({
      identity: "Fido",
      applied: 2,
      skipped: 0,
      skips: [],
    });

    const onReviewed = vi.fn();

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={onReviewed} />);

    const alternateButton = await screen.findByRole("button", {
      name: /approve 2 as fido \(62%\)/i,
    });
    fireEvent.click(alternateButton);

    await waitFor(() => {
      expect(api.reassignCluster).toHaveBeenCalledWith("Fido", "dog", [1, 2]);
    });

    expect(onReviewed).toHaveBeenCalled();
    expect(await screen.findByText(/approved 2 as fido/i)).toBeInTheDocument();
  });

  it("shows no alternate-identity buttons when the representative has none", async () => {
    const group = buildGroup();
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    await screen.findByRole("button", { name: /approve 2 as rex/i });

    expect(
      screen.queryByRole("button", { name: /approve 2 as (?!rex)/i }),
    ).not.toBeInTheDocument();
  });

  it("rejects the selected members without touching the reviewed stat", async () => {
    const group = buildGroup();
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.rejectCluster).mockResolvedValue({
      identity: "Rex",
      applied: 2,
      skipped: 0,
      skips: [],
    });

    const onReviewed = vi.fn();

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={onReviewed} />);

    const rejectButton = await screen.findByRole("button", { name: /not rex/i });
    fireEvent.click(rejectButton);

    await waitFor(() => {
      expect(api.rejectCluster).toHaveBeenCalledWith("Rex", "dog", [1, 2]);
    });

    expect(onReviewed).not.toHaveBeenCalled();
  });

  it("lets the reviewer split a mixed group into individual review", async () => {
    const group = buildGroup();
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.correctClassification).mockResolvedValue(undefined);

    const onReviewed = vi.fn();

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={onReviewed} />);

    fireEvent.click(await screen.findByRole("button", { name: /multiple dogs here/i }));

    expect(await screen.findByText(/reviewing individually: 1 of 2/i)).toBeInTheDocument();

    // Correct the first member to Rex individually -- the same write path
    // Queue mode uses, not a group approval.
    fireEvent.click(screen.getByRole("button", { name: "Rex (predicted)" }));

    await waitFor(() => {
      expect(api.correctClassification).toHaveBeenCalledWith(1, "Rex");
    });

    expect(onReviewed).toHaveBeenCalled();
    expect(await screen.findByText(/reviewing individually: 1 of 1/i)).toBeInTheDocument();
  });

  it("returns to the group list from the split view", async () => {
    const group = buildGroup();
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /multiple dogs here/i }));
    expect(await screen.findByRole("button", { name: /back to groups/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /back to groups/i }));

    expect(await screen.findByText("Rex")).toBeInTheDocument();
    expect(api.getReviewGroups).toHaveBeenCalledTimes(2);
  });
});
