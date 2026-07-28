export interface ReviewItem {
  classification_id: number;
  crop_id: number;
  path: string;

  prediction: {
    identity: string | null;
    similarity: number;
  };

  suggestion: {
    identity: string;
    similarity: number;
    example_id: string;
  } | null;
}

export interface ReviewQueueStats {
  total: number;
  reviewed: number;
  remaining: number;
}