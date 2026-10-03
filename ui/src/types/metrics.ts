export interface ClassificationPassSummary {
  id: number;
  status: string;
  classifier_version: string;
  threshold: number;
  eligible_count: number;
  confident_count: number;
  needs_review_count: number;
  unknown_count: number;
  changed_count: number;
  labeled_example_count: number | null;
  review_queue_size: number | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DetectionCoverage {
  scanned_count: number;
  processed_count: number;
  with_dog_count: number;
  with_dog_rate: number | null;
  with_cat_count: number;
  with_cat_rate: number | null;
  awaiting_detection_count: number;
  unprocessable_count: number;
}

export interface SpeciesTimelinePoint {
  label: string;
  counts: Record<string, number>;
}

export interface SpeciesTimeline {
  species: string;
  // Stacking order: top pets by total volume, "Other" last if present.
  identities: string[];
  points: SpeciesTimelinePoint[];
}

export interface LearningMetrics {
  eligible_count: number;
  reviewed_count: number;
  labeled_example_count: number;
  confident_count: number;
  needs_review_count: number;
  unknown_count: number;
  coverage: number | null;
  review_rate: number | null;
  unknown_rate: number | null;
  review_queue_size: number;
  no_review_needed_count: number;
  automation_rate: number | null;
  last_reclassification: ClassificationPassSummary | null;
  pass_history: ClassificationPassSummary[];
  detection_coverage: DetectionCoverage;
}

export interface FriendNode {
  id: number;
  name: string;
  species: "dog" | "cat";
  /** Distinct photos with a confirmed occurrence of this pet. */
  image_count: number;
  /** Crop to show as this pet's thumbnail; null when no eligible crop exists. */
  key_crop_id: number | null;
}

export interface FriendEdge {
  a_id: number;
  b_id: number;
  /** Distinct photos both pets appear in. */
  count: number;
}

export interface FriendsInFrame {
  nodes: FriendNode[];
  edges: FriendEdge[];
}
