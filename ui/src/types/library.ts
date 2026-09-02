import type { ReviewItem } from "./review";

/**
 * How `GET /api/library` orders its filtered, paginated result set. A
 * superset of `ClusterSort` (types/clusters.ts) plus a reviewed-date axis
 * (issue #225) -- kept separate because "reviewed date" has no meaning for
 * the cluster-approval workspace's pending-recommendation pools, which stay
 * on `ClusterSort` alone.
 */
export type LibrarySort =
  | "captured_asc"
  | "captured_desc"
  | "confidence_desc"
  | "confidence_asc"
  | "reviewed_desc"
  | "reviewed_asc";

export interface LibraryEntry {
  item: ReviewItem;
  reviewed: boolean;
  reviewed_at: string | null;
}

export interface LibraryPage {
  items: LibraryEntry[];
  total: number;
  limit: number;
  offset: number;
}
