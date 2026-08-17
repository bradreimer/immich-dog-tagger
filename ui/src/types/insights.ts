export interface PlaceCount {
  label: string;
  city: string | null;
  state: string | null;
  country: string | null;
  count: number;
}

export interface PersonCount {
  label: string;
  person_id: string;
  name: string | null;
  count: number;
}

export interface TimelineEntry {
  asset_id: number;
  immich_asset_id: string;
  captured_at: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  confidence: number;
  source: string;
}

export interface InsightsSummary {
  identity_id: number;
  identity_name: string;
  total_photos: number;
  first_seen: string | null;
  last_seen: string | null;
  photos_by_year: Record<string, number>;
  top_place: PlaceCount | null;
  top_person: PersonCount | null;
  favorite_photo_count: number;
}

// A single fun fact produced by a pluggable InsightProvider (ADR-005).
// New providers appear here automatically -- no type/UI change needed
// per insight, only per new `category`.
export interface InsightCard {
  slug: string;
  title: string;
  value: string;
  subtext: string | null;
  category: "volume" | "place" | "social" | "milestone" | "time";
}
