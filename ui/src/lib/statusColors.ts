import type { JobStatus } from "../types/jobs";

/**
 * Single source of truth for status -> color mapping, so "failed" (etc.) renders as the same
 * color on the Job Queue page, Overview's recent-jobs list, and the Metrics donut/trend
 * chart. See docs/specs/v1.2-visual-style-refresh.md FR-3.
 */
const CARD_CLASS: Record<JobStatus, string> = {
  running: "border-status-info/40 bg-status-info/5",
  completed: "border-status-good/40 bg-status-good/5",
  failed: "border-status-critical/40 bg-status-critical/5",
  pending: "border-status-warning/40 bg-status-warning/5",
  canceled: "border-muted-foreground/30 bg-muted/40",
};

const BADGE_CLASS: Record<JobStatus, string> = {
  running: "border-transparent bg-status-info text-white",
  completed: "border-transparent bg-status-good text-white",
  failed: "border-transparent bg-status-critical text-white",
  pending: "border-transparent bg-status-warning text-black/80",
  canceled: "border-transparent bg-muted-foreground text-white",
};

const TEXT_CLASS: Record<JobStatus, string> = {
  running: "text-status-info",
  completed: "text-status-good",
  failed: "text-status-critical",
  pending: "text-status-warning",
  canceled: "text-muted-foreground",
};

export function jobCardClassName(status: JobStatus): string {
  return CARD_CLASS[status] ?? "";
}

export function jobBadgeClassName(status: JobStatus): string {
  return BADGE_CLASS[status] ?? "";
}

export function jobTextClassName(status: JobStatus): string {
  return TEXT_CLASS[status] ?? "";
}
