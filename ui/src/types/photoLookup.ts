export interface PhotoLookupDetection {
  detection_id: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  species: string;
  crop_id: number | null;
  classification_id: number | null;
  identity: string | null;
  confidence: number | null;
}

export interface PhotoLookupResult {
  asset_id: number;
  immich_asset_id: string;
  captured_at: string | null;
  detections: PhotoLookupDetection[];
}
