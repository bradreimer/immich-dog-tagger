import type { ReviewItem } from "./review";

/**
 * How the cluster list and each cluster's members are ordered (issue #143).
 * Default is "confidence_desc" -- approve the surest group first.
 */
export type ClusterSort =
  | "captured_asc"
  | "captured_desc"
  | "confidence_desc"
  | "confidence_asc";

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
  sort: ClusterSort;
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
