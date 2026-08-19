import type { ReviewItem } from "./review";

/** A pooled candidate that could not be clustered, and why. */
export interface ExcludedCandidate {
  classification_id: number;
  crop_id: number;
  reason: string;
}

export interface RecommendationCluster {
  id: number;
  size: number;
  representative: ReviewItem;
  members: ReviewItem[];
  min_similarity: number;
  max_similarity: number;
  earliest_captured_at: string | null;
  latest_captured_at: string | null;
}

export interface ClusterProposal {
  identity: string;
  species: string;
  clusters: RecommendationCluster[];
  excluded: ExcludedCandidate[];
  candidate_count: number;
  clustered_count: number;
  distance_threshold: number;
  truncated: boolean;
}

export interface ApprovalSkip {
  classification_id: number;
  reason: string;
}

export interface ClusterApprovalResult {
  identity: string;
  applied: number;
  skipped: number;
  skips: ApprovalSkip[];
}
