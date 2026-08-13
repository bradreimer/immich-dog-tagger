export interface ReviewSuggestion {
  identity: string;
  similarity: number;
  example_id: number;
  example_path: string;
  captured_at: string | null;
}

export interface ReviewItem {
  classification_id: number;
  crop_id: number;
  path: string;
  filename: string;
  species: string;
  reason: string;

  prediction: {
    identity: string | null;
    similarity: number;
    candidates: ReviewCandidate[];
  };

  suggestion: ReviewSuggestion | null;
}

export interface ReviewQueueStats {
  total: number;
  reviewed: number;
  remaining: number;
}

export interface ReviewCandidate {
  identity: string;
  similarity: number;
  matched_example_id: number;
}