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
    sort: "confidence_desc",
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

  it("approves only the members left selected", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.approveCluster).mockResolvedValue({
      identity: "Hermann",
      applied: 2,
      skipped: 0,
      skips: [],
    });

    render(<ClusterPanel identity="Hermann" species="dog" />);

    // The odd photo out: deselected before approving.
    fireEvent.click(await screen.findByRole("checkbox", { name: "2.jpg" }));

    expect(screen.getByRole("checkbox", { name: "2.jpg" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByText("2 of 3 selected")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Approve 2 photos as Hermann" }),
    );

    await waitFor(() => {
      expect(api.approveCluster).toHaveBeenCalledWith("Hermann", "dog", [1, 3]);
    });
  });

  it("puts the count it will apply to on the approve control", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    expect(await screen.findByText("Approve 3 photos")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "1.jpg" }));

    expect(screen.getByText("Approve 2 photos")).toBeInTheDocument();
  });

  it("selects none and then all again within a cluster", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(await screen.findByRole("button", { name: "Select none" }));

    expect(screen.getByText("0 of 3 selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Select all" }));

    expect(screen.getByText("3 of 3 selected")).toBeInTheDocument();
  });

  it("disables approve rather than submitting an empty approval", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(await screen.findByRole("button", { name: "Select none" }));

    const approve = screen.getByRole("button", {
      name: "Approve 0 photos as Hermann",
    });

    expect(approve).toBeDisabled();

    fireEvent.click(approve);

    expect(api.approveCluster).not.toHaveBeenCalled();
  });

  it("clears the selection when the pet changes", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    const { rerender } = render(<ClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(await screen.findByRole("button", { name: "Select none" }));

    expect(screen.getByText("0 of 3 selected")).toBeInTheDocument();

    rerender(<ClusterPanel identity="Otto" species="dog" />);

    // The hardest case: the new pet's clusters happen to carry the same ids,
    // so nothing about the cluster itself signals the change. A stale
    // selection must never carry across pets even then.
    expect(await screen.findByText("3 of 3 selected")).toBeInTheDocument();
  });

  it("reveals the members a large cluster collapses, so each can be deselected", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(
      buildProposal({ clusters: [buildCluster(1, 13)] }),
    );

    render(<ClusterPanel identity="Hermann" species="dog" />);

    expect(screen.queryByRole("checkbox", { name: "13.jpg" })).not.toBeInTheDocument();

    fireEvent.click(
      await screen.findByRole("button", { name: "Show all 13 photos in this group" }),
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "13.jpg" }));

    expect(screen.getByText("12 of 13 selected")).toBeInTheDocument();
  });

  it("shows the current sort at a glance and defaults to surest first", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    expect(await screen.findByText("3 photos")).toBeInTheDocument();

    expect(api.getPetClusters).toHaveBeenCalledWith(
      "Hermann",
      "dog",
      "confidence_desc",
    );

    const select = screen.getByLabelText("Sort") as HTMLSelectElement;

    expect(select.value).toBe("confidence_desc");
  });

  it("re-fetches with the chosen sort and reflects it once loaded", async () => {
    vi.mocked(api.getPetClusters).mockResolvedValue(buildProposal());

    render(<ClusterPanel identity="Hermann" species="dog" />);

    await screen.findByText("3 photos");

    vi.mocked(api.getPetClusters).mockResolvedValue(
      buildProposal({ sort: "captured_asc" }),
    );

    fireEvent.change(screen.getByLabelText("Sort"), {
      target: { value: "captured_asc" },
    });

    await waitFor(() => {
      expect(api.getPetClusters).toHaveBeenCalledWith(
        "Hermann",
        "dog",
        "captured_asc",
      );
    });

    expect((screen.getByLabelText("Sort") as HTMLSelectElement).value).toBe(
      "captured_asc",
    );
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
