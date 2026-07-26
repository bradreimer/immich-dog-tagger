export interface ReviewItem {
  classification_id: number;
  crop_id: number;
  identity: string | null;
  confidence: number;
  path: string;
  matched_example_path: string | null;
}