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

/**
 * A cluster member whose own top-ranked, time/location-weighted prediction
 * is not the group's identity -- it was pooled in by raw visual similarity,
 * not because the group's identity is actually its best match once capture
 * time/location are weighed in. `reason` is the same
 * `temporal-mismatch`/`location-mismatch` vocabulary Queue mode's
 * `ReviewItem.reason` already uses, plus `different-top-prediction` when
 * neither weight alone explains it.
 */
export interface GroupMismatch {
  classification_id: number;
  reason: string;
}

/**
 * One identity's cluster, carrying the identity/species it belongs to
 * (Review tab Grouped mode) -- unlike a Library `ClusterProposal`, which is
 * already scoped to one pet by the request, a `ReviewGroup` can be for any
 * pet with pending queue work, so it names its own identity/species.
 */
export interface ReviewGroup {
  identity: string;
  species: string;
  cluster: RecommendationCluster;
  mismatches: GroupMismatch[];
}

export interface ReviewGroupsProposal {
  groups: ReviewGroup[];
  identity_count: number;
  truncated_identities: boolean;
  sort: ClusterSort;
}
