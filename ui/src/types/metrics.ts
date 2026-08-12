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
}
