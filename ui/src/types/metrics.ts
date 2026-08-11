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
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
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
  last_reclassification: ClassificationPassSummary | null;
  pass_history: ClassificationPassSummary[];
}
