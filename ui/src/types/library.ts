import type { ReviewItem } from "./review";

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
