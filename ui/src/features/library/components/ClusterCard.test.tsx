import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

import { ClusterCard } from "./ClusterCard";
import type { RecommendationCluster } from "@/types/clusters";
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
});
