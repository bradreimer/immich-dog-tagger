import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ReviewGroupedPanel } from "./ReviewGroupedPanel";
import * as api from "../../../lib/api";
import type { ReviewGroup } from "../../../types/clusters";
import type { ReviewItem } from "../../../types/review";
import type { Dog } from "../../../types/dogs";

vi.mock("../../../lib/api", () => ({
  ClassificationNotFoundError: class extends Error {},
  CropNotFoundError: class extends Error {},
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
const FIDO: Dog = { id: 2, name: "Fido", species: "dog", active: true };
const TOM: Dog = { id: 3, name: "Tom", species: "cat", active: true };

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
    account: null,
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
    mismatches: [],
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

    expect(await screen.findByRole("heading", { name: "Rex" })).toBeInTheDocument();
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

    fireEvent.click(await screen.findByRole("button", { name: "Rex (predicted)" }));

    await waitFor(() => {
      expect(api.approveCluster).toHaveBeenCalledWith("Rex", "dog", [1, 2]);
    });

    expect(onReviewed).toHaveBeenCalled();
    expect(await screen.findByText(/approved 2 as rex/i)).toBeInTheDocument();
  });

  it("reassigns the group when choosing a different identity", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
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

    render(
      <ReviewGroupedPanel dogs={[REX, FIDO, TOM]} immichUrl={null} onReviewed={onReviewed} />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Fido" }));

    await waitFor(() => {
      expect(api.reassignCluster).toHaveBeenCalledWith("Fido", "dog", [1, 2]);
    });

    expect(api.approveCluster).not.toHaveBeenCalled();
    expect(onReviewed).toHaveBeenCalled();
    expect(await screen.findByText(/approved 2 as fido/i)).toBeInTheDocument();
    // Only same-species identities are offered.
    expect(screen.queryByRole("button", { name: "Tom" })).not.toBeInTheDocument();
  });

  it("shows one group at a time and navigates between them", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [
        buildGroup(),
        buildGroup({
          identity: "Fido",
          cluster: { ...buildGroup().cluster, id: 3 },
        }),
      ],
      identity_count: 2,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX, FIDO]} immichUrl={null} onReviewed={vi.fn()} />);

    expect(await screen.findByText("Group 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rex" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Fido" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next group/i }));
    expect(screen.getByText("Group 2 of 2")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fido" })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByText("Group 1 of 2")).toBeInTheDocument();
  });

  it("applies a keyboard identity choice to the selection", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
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

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    await screen.findByText("Group 1 of 1");
    fireEvent.keyDown(window, { key: "1" });

    await waitFor(() => {
      expect(api.approveCluster).toHaveBeenCalledWith("Rex", "dog", [1, 2]);
    });
  });

  it("skips only the selected members", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.skipClassification).mockResolvedValue(undefined);

    const onReviewed = vi.fn();

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={onReviewed} />);

    fireEvent.click(await screen.findByRole("button", { name: "Deselect photo 2" }));
    fireEvent.click(screen.getByRole("button", { name: /skip/i }));

    await waitFor(() => {
      expect(api.skipClassification).toHaveBeenCalledWith(1);
    });

    expect(api.skipClassification).toHaveBeenCalledTimes(1);
    expect(onReviewed).toHaveBeenCalled();
    expect(await screen.findByText("Skipped 1.")).toBeInTheDocument();
  });

  it("corrects the species of every selected member", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.correctSpecies).mockResolvedValue(buildItem({ species: "cat" }));

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Cat" }));

    await waitFor(() => {
      expect(api.correctSpecies).toHaveBeenCalledTimes(2);
    });

    expect(api.correctSpecies).toHaveBeenCalledWith(1, "cat");
    expect(api.correctSpecies).toHaveBeenCalledWith(2, "cat");
    expect(await screen.findByText("Changed 2 to cat.")).toBeInTheDocument();
  });

  it("marks selected members as not a dog or cat, skipping stale crops", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [
        buildGroup({
          cluster: {
            ...buildGroup().cluster,
            members: [
              buildItem({ classification_id: 1, crop_id: 11 }),
              buildItem({ classification_id: 2, crop_id: 12 }),
            ],
          },
        }),
      ],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });
    vi.mocked(api.markCropNotAnimal)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new api.CropNotFoundError("gone"));

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /not a dog or cat/i }));

    await waitFor(() => {
      expect(api.markCropNotAnimal).toHaveBeenCalledTimes(2);
    });

    expect(api.markCropNotAnimal).toHaveBeenCalledWith(11);
    expect(api.markCropNotAnimal).toHaveBeenCalledWith(12);
    expect(
      await screen.findByText(/marked 1 as not a dog or cat, skipped 1/i),
    ).toBeInTheDocument();
  });

  it("disables group actions when nothing is selected", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /select none/i }));

    expect(screen.getByRole("button", { name: "Rex (predicted)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /skip/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /not rex/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /multiple dogs here/i })).toBeEnabled();
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

    await waitFor(() => {
      expect(api.getReviewGroups).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Rex" })).toBeInTheDocument();
    });
  });

  it("links each member to Immich without toggling its selection", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(
      <ReviewGroupedPanel dogs={[REX]} immichUrl="https://immich.test" onReviewed={vi.fn()} />,
    );

    const links = await screen.findAllByRole("link", { name: /view in immich/i });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "https://immich.test/photos/asset-1");

    fireEvent.click(links[0]);
    expect(screen.getByText("2 of 2 selected")).toBeInTheDocument();
  });

  it("omits the Immich links when no Immich URL is configured", async () => {
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [buildGroup()],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    await screen.findByRole("heading", { name: "Rex" });
    expect(screen.queryByRole("link", { name: /view in immich/i })).not.toBeInTheDocument();
  });

  it("shows the group's earliest and latest capture dates", async () => {
    const group = buildGroup();
    group.cluster.earliest_captured_at = "2024-03-02T12:00:00Z";
    group.cluster.latest_captured_at = "2026-01-05T12:00:00Z";
    vi.mocked(api.getReviewGroups).mockResolvedValue({
      groups: [group],
      identity_count: 1,
      truncated_identities: false,
      sort: "confidence_desc",
    });

    render(<ReviewGroupedPanel dogs={[REX]} immichUrl={null} onReviewed={vi.fn()} />);

    expect(await screen.findByText(/March 2, 2024 – January 5, 2026/)).toBeInTheDocument();
  });
});
