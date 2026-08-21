import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ClusterCard } from "./ClusterCard";
import type { RecommendationCluster } from "@/types/clusters";
import type { Dog } from "@/types/dogs";
import type { ReviewItem } from "@/types/review";

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

function buildCluster(size: number): RecommendationCluster {
  const members = Array.from({ length: size }, (_, index) => buildMember(index + 1));

  return {
    id: 1,
    size,
    representative: members[0],
    members,
    min_similarity: 0.72,
    max_similarity: 0.88,
    earliest_captured_at: "2024-05-01T00:00:00Z",
    latest_captured_at: "2026-01-05T00:00:00Z",
  };
}

describe("ClusterCard", () => {
  // Regression test for issue #164: a dog with hundreds of pending photos
  // can produce dozens of clusters, each mounting a representative image
  // plus up to 11 member thumbnails as plain <img> tags. Without native
  // lazy-loading, every one of those fires its GET /crops/{id} request the
  // instant the card mounts, and a burst that size exhausts the shared
  // SQLAlchemy connection pool for the whole app. Every crop <img> must
  // defer off-screen loads to the browser instead of firing eagerly.
  it("marks every crop thumbnail as lazy so off-screen images do not fetch eagerly", () => {
    const { container } = render(
      <ClusterCard
        cluster={buildCluster(11)}
        identity="Hermann"
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    // The representative image plus every visible member thumbnail. Member
    // thumbnails have alt="" (decorative), so they must be queried directly
    // rather than via an accessible-name role query.
    const images = container.querySelectorAll("img");

    expect(images.length).toBeGreaterThan(1);

    for (const image of images) {
      expect(image).toHaveAttribute("loading", "lazy");
    }
  });

  // Coverage for issue #166: the cluster is correctly grouped as one animal,
  // but the wrong identity was proposed for it, so the owner reassigns it
  // directly rather than rejecting it back into the pending queue.
  describe("reassigning to another pet", () => {
    const otherPets: Dog[] = [
      { id: 2, name: "Otto", species: "dog", active: true },
      { id: 3, name: "Rex", species: "dog", active: true },
    ];

    it("offers no reassignment control when there is no other pet to offer", () => {
      render(
        <ClusterCard
          cluster={buildCluster(2)}
          identity="Hermann"
          onApprove={vi.fn()}
          onReject={vi.fn()}
        />,
      );

      expect(screen.queryByText("Select another pet…")).not.toBeInTheDocument();
    });

    it("assigns only the selected members to the chosen pet", async () => {
      const onReassign = vi.fn().mockResolvedValue(undefined);

      render(
        <ClusterCard
          cluster={buildCluster(3)}
          identity="Hermann"
          onApprove={vi.fn()}
          onReject={vi.fn()}
          otherPets={otherPets}
          onReassign={onReassign}
        />,
      );

      // Deselect one member before reassigning the rest.
      fireEvent.click(screen.getByRole("checkbox", { name: "2.jpg" }));

      fireEvent.change(screen.getByDisplayValue("Select another pet…"), {
        target: { value: "Otto" },
      });

      fireEvent.click(screen.getByRole("button", { name: "Assign 2 photos to Otto" }));

      expect(onReassign).toHaveBeenCalledWith("Otto", [1, 3]);
    });

    it("disables Assign until a pet is chosen", () => {
      render(
        <ClusterCard
          cluster={buildCluster(3)}
          identity="Hermann"
          onApprove={vi.fn()}
          onReject={vi.fn()}
          otherPets={otherPets}
          onReassign={vi.fn()}
        />,
      );

      expect(
        screen.getByRole("button", { name: "Assign 3 photos to another pet" }),
      ).toBeDisabled();
    });

    it("surfaces a reassignment failure without losing the cluster", async () => {
      const onReassign = vi.fn().mockRejectedValue(new Error("Failed to reassign"));

      render(
        <ClusterCard
          cluster={buildCluster(3)}
          identity="Hermann"
          onApprove={vi.fn()}
          onReject={vi.fn()}
          otherPets={otherPets}
          onReassign={onReassign}
        />,
      );

      fireEvent.change(screen.getByDisplayValue("Select another pet…"), {
        target: { value: "Rex" },
      });

      fireEvent.click(screen.getByRole("button", { name: "Assign 3 photos to Rex" }));

      expect(await screen.findByText("Failed to reassign")).toBeInTheDocument();
      expect(screen.getByText("3 photos")).toBeInTheDocument();
    });
  });
});
