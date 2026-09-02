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
  not_animal: boolean;
}

export interface PhotoLookupResult {
  asset_id: number;
  immich_asset_id: string;
  captured_at: string | null;
  detections: PhotoLookupDetection[];
}

/** Result of forcing one asset back through download/detect/classify (issue #226). */
export interface AssetRepairResult {
  asset_id: number;
  immich_asset_id: string;
  status: string;
  detections: number;
  dogs: number;
  cats: number;
  classified: number;
  message: string;
}
