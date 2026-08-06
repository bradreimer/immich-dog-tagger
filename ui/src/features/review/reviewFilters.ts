import type { ReviewFilter } from "./types";

export function getReviewQuery(filter: ReviewFilter) {
  switch (filter) {
    case "unknown":
      return {
        unknown: true,
      };

    case "low-confidence":
      return {
        confidence_below: 0.5,
      };

    case "candidate-conflict":
      return {
        candidate_conflict: true,
      };

    case "all":
    default:
      return {};
  }
}