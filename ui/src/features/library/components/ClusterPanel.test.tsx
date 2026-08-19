import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ClusterPanel } from "./ClusterPanel";
import * as api from "@/lib/api";
import type { ClusterProposal, RecommendationCluster } from "@/types/clusters";
import type { ReviewItem } from "@/types/review";

vi.mock("@/lib/api", () => ({
  getPetClusters: vi.fn(),
  approveCluster: vi.fn(),
}));

function buildMember(classificationId: number): ReviewItem {
  return {
    classification_id: classificationId,
    crop_id: classificationId,
    path: `/crops/${classificationId}.jpg`,
    filename: `${classificationId}.jpg`,
    species: "dog",
    reason: "review",
    captured_at: "2026-01-05T12:00:00Z",
    immich_asset_id: `asset-${classificationId}`,
    prediction: {
      identity: "Hermann",
      similarity: 0.72,
      candidates: [],
    },
    suggestion: null,
  };
}

function buildCluster(id: number, size: number): RecommendationCluster {
  const members = Array.from({ length: size }, (_, index) => buildMember(id + index));

  return {
    id,
    size,
    representative: members[0],
    members,
    min_similarity: 0.72,
    max_similarity: 0.88,
    earliest_captured_at: "2024-05-01T00:00:00Z",
    latest_captured_at: "2026-01-05T00:00:00Z",
  };
}

function buildProposal(overrides: Partial<ClusterProposal> = {}): ClusterProposal {
  const clusters = overrides.clusters ?? [buildCluster(1, 3)];

  return {
    identity: "Hermann",
    species: "dog",
    clusters,
    excluded: [],
    candidate_count: clusters.reduce((total, cluster) => total + cluster.size, 0),
    clustered_count: clusters.reduce((total, cluster) => total + cluster.size, 0),
    distance_threshold: 0.2,
    truncated: false,
    ...overrides,
  };
}

describe("ClusterPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a cluster with its count, confidence range, and capture-date range", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    expect(await screen.findByText("3 photos")).toBeInTheDocument();
    expect(screen.getByText("72-88% confidence")).toBeInTheDocument();
    expect(screen.getByText(/May 1, 2024/)).toBeInTheDocument();
    expect(screen.getByText("3 pending photos in 1 group")).toBeInTheDocument();
  });

  it("approves every member of a cluster in one action", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.approveCluster).mockResolvedValue({
      identity: "Hermann",
      applied: 3,
      skipped: 0,
      skips: [],
    });

    const onApproved = vi.fn();

    render(<ClusterPanel identity="Hermann" species="dog" onApproved={onApproved} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Approve 3 photos as Hermann" }),
    );

    await waitFor(() => {
      expect(api.approveCluster).toHaveBeenCalledWith("Hermann", "dog", [1, 2, 3]);
    });

    expect(await screen.findByText("Tagged 3 photos as Hermann.")).toBeInTheDocument();
    expect(onApproved).toHaveBeenCalledWith(3);
    // The pool is re-read afterwards, so approved photos leave the panel.
    expect(api.getPetClusters).toHaveBeenCalledTimes(2);
  });

  it("reports what an approval skipped and why", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.approveCluster).mockResolvedValue({
      identity: "Hermann",
      applied: 2,
      skipped: 1,
      skips: [{ classification_id: 3, reason: "already-reviewed" }],
    });

    render(<ClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Approve 3 photos as Hermann" }),
    );

    expect(
      await screen.findByText(
        "Tagged 2 of 3 photos as Hermann. Skipped 1: already-reviewed.",
      ),
    ).toBeInTheDocument();
  });

  it("shows an explicit empty state for a pet with no pending candidates", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal({ clusters: [] }));

    render(<ClusterPanel identity="Hermann" species="dog" />);

    expect(
      await screen.findByText(/No pending recommendations for Hermann/),
    ).toBeInTheDocument();
  });

  it("reports candidates that could not be grouped", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(
      buildProposal({
        excluded: [{ classification_id: 9, crop_id: 9, reason: "no-embedding" }],
      }),
    );

    render(<ClusterPanel identity="Hermann" species="dog" />);

    expect(
      await screen.findByText(/1 photo has no stored embedding/),
    ).toBeInTheDocument();
  });

  it("retries after a failed load", async () => {
    vi.mocked(api.getPetClusters)
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByText("3 photos")).toBeInTheDocument();
  });

  it("surfaces an approval failure without losing the cluster", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.approveCluster).mockRejectedValue(new Error("Failed to approve cluster"));

    render(<ClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Approve 3 photos as Hermann" }),
    );

    expect(await screen.findByText("Failed to approve cluster")).toBeInTheDocument();
    expect(screen.getByText("3 photos")).toBeInTheDocument();
  });
});
