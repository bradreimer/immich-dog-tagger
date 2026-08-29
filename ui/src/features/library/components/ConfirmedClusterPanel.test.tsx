import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ConfirmedClusterPanel } from "./ConfirmedClusterPanel";
import * as api from "@/lib/api";
import type { ClusterProposal, RecommendationCluster } from "@/types/clusters";
import type { ReviewItem } from "@/types/review";

vi.mock("@/lib/api", () => ({
  getConfirmedClusters: vi.fn(),
  moveConfirmedPhotos: vi.fn(),
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
      similarity: 0.9,
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
    min_similarity: 0.85,
    max_similarity: 0.97,
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

const identities = [
  { id: 1, name: "Hermann", species: "dog" as const, active: true },
  { id: 2, name: "Otto", species: "dog" as const, active: true },
];

describe("ConfirmedClusterPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a cluster with its count, confidence range, and capture-date range", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());

    render(<ConfirmedClusterPanel identity="Hermann" species="dog" />);

    expect(await screen.findByText("3 photos")).toBeInTheDocument();
    expect(screen.getByText("85-97% confidence")).toBeInTheDocument();
    expect(screen.getByText("3 confirmed photos in 1 group")).toBeInTheDocument();
  });

  it("requests the confirmed pool, not the pending one", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());

    render(<ConfirmedClusterPanel identity="Hermann" species="dog" />);

    await screen.findByText("3 photos");

    expect(api.getConfirmedClusters).toHaveBeenCalledWith(
      "Hermann",
      "dog",
      "confidence_desc",
    );
  });

  it("renders no approve or reject control -- only the move action applies here", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());

    render(
      <ConfirmedClusterPanel identity="Hermann" species="dog" identities={identities} />,
    );

    await screen.findByText("3 photos");

    expect(
      screen.queryByRole("button", { name: /^Approve/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Not Hermann/ })).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Move 3 photos to another pet" }),
    ).toBeInTheDocument();
  });

  it("moves the selection to a different pet via the dedicated move endpoint", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.moveConfirmedPhotos).mockResolvedValue({
      identity: "Otto",
      applied: 3,
      skipped: 0,
      skips: [],
    });

    const onMoved = vi.fn();

    render(
      <ConfirmedClusterPanel
        identity="Hermann"
        species="dog"
        identities={identities}
        onMoved={onMoved}
      />,
    );

    await screen.findByText("3 photos");

    fireEvent.change(screen.getByDisplayValue("Select another pet…"), {
      target: { value: "Otto" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Move 3 photos to Otto" }));

    await waitFor(() => {
      expect(api.moveConfirmedPhotos).toHaveBeenCalledWith("Hermann", "Otto", "dog", [
        1, 2, 3,
      ]);
    });

    expect(await screen.findByText("Moved 3 photos to Otto.")).toBeInTheDocument();
    expect(onMoved).toHaveBeenCalledWith(3);
    // The pool is re-read afterwards, same as an approval/reassignment.
    expect(api.getConfirmedClusters).toHaveBeenCalledTimes(2);
  });

  it("moves only the members left selected", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.moveConfirmedPhotos).mockResolvedValue({
      identity: "Otto",
      applied: 2,
      skipped: 0,
      skips: [],
    });

    render(
      <ConfirmedClusterPanel identity="Hermann" species="dog" identities={identities} />,
    );

    await screen.findByText("3 photos");

    fireEvent.click(screen.getByRole("checkbox", { name: "2.jpg" }));

    fireEvent.change(screen.getByDisplayValue("Select another pet…"), {
      target: { value: "Otto" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Move 2 photos to Otto" }));

    await waitFor(() => {
      expect(api.moveConfirmedPhotos).toHaveBeenCalledWith(
        "Hermann",
        "Otto",
        "dog",
        [1, 3],
      );
    });
  });

  it("reports what a move skipped and why", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.moveConfirmedPhotos).mockResolvedValue({
      identity: "Otto",
      applied: 2,
      skipped: 1,
      skips: [{ classification_id: 3, reason: "not-source-pet" }],
    });

    render(
      <ConfirmedClusterPanel identity="Hermann" species="dog" identities={identities} />,
    );

    await screen.findByText("3 photos");

    fireEvent.change(screen.getByDisplayValue("Select another pet…"), {
      target: { value: "Otto" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Move 3 photos to Otto" }));

    expect(
      await screen.findByText(
        "Moved 2 of 3 photos to Otto. Skipped 1: not-source-pet.",
      ),
    ).toBeInTheDocument();
  });

  it("shows no move control when no other pet of this species is configured", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());

    render(<ConfirmedClusterPanel identity="Hermann" species="dog" />);

    await screen.findByText("3 photos");

    expect(screen.queryByText("Select another pet…")).not.toBeInTheDocument();
  });

  it("re-fetches with the chosen sort", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());

    render(<ConfirmedClusterPanel identity="Hermann" species="dog" />);

    await screen.findByText("3 photos");

    vi.mocked(api.getConfirmedClusters).mockResolvedValue(
      buildProposal({ sort: "captured_asc" }),
    );

    fireEvent.change(screen.getByLabelText("Sort"), {
      target: { value: "captured_asc" },
    });

    await waitFor(() => {
      expect(api.getConfirmedClusters).toHaveBeenCalledWith(
        "Hermann",
        "dog",
        "captured_asc",
      );
    });
  });

  it("shows an explicit empty state for a pet with no confirmed photos", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal({ clusters: [] }));

    render(<ConfirmedClusterPanel identity="Hermann" species="dog" />);

    expect(
      await screen.findByText(/No confirmed photos for Hermann yet/),
    ).toBeInTheDocument();
  });

  it("retries after a failed load", async () => {
    vi.mocked(api.getConfirmedClusters)
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(buildProposal());

    render(<ConfirmedClusterPanel identity="Hermann" species="dog" />);

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByText("3 photos")).toBeInTheDocument();
  });

  it("surfaces a move failure without losing the cluster", async () => {
    vi.mocked(api.getConfirmedClusters).mockResolvedValue(buildProposal());
    vi.mocked(api.moveConfirmedPhotos).mockRejectedValue(new Error("Failed to move photos"));

    render(
      <ConfirmedClusterPanel identity="Hermann" species="dog" identities={identities} />,
    );

    await screen.findByText("3 photos");

    fireEvent.change(screen.getByDisplayValue("Select another pet…"), {
      target: { value: "Otto" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Move 3 photos to Otto" }));

    expect(await screen.findByText("Failed to move photos")).toBeInTheDocument();
    expect(screen.getByText("3 photos")).toBeInTheDocument();
  });
});
