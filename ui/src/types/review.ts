export interface ReviewSuggestion {
  identity: string;
  similarity: number;
  example_id: number;
  example_path: string;
}

export interface ReviewItem {
  classification_id: number;
  crop_id: number;
  path: string;
  filename: string;

  prediction: {
    identity: string | null;
    similarity: number;
  };

  suggestion: ReviewSuggestion | null;
}

export interface ReviewQueueStats {
  total: number;
  reviewed: number;
  remaining: number;
}

export type ReviewFilter =
  | "all"
  | "unknown"
  | "low-confidence";