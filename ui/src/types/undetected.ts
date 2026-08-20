export interface UndetectedAsset {
  asset_id: number;
  immich_asset_id: string;
  captured_at: string | null;
  identities: string[];
}

export interface UndetectedAssetPage {
  items: UndetectedAsset[];
  total: number;
  limit: number;
  offset: number;
}
