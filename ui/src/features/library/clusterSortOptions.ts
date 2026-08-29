import type { ClusterSort } from "@/types/clusters";

/**
 * The four orders issue #143 defines, in a fixed display order. Shared by
 * the pending-recommendations panel and v1.10's confirmed-photos panel, so
 * both sort controls read the same way.
 */
export const CLUSTER_SORT_OPTIONS: { value: ClusterSort; label: string }[] = [
  { value: "confidence_desc", label: "Surest first" },
  { value: "confidence_asc", label: "Least sure first" },
  { value: "captured_desc", label: "Newest first" },
  { value: "captured_asc", label: "Oldest first" },
];

export const DEFAULT_CLUSTER_SORT: ClusterSort = "confidence_desc";
