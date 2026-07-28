import type {
  ReviewItem,
  ReviewQueueStats,
} from "./types";

export async function getReview(): Promise<ReviewItem[]> {
  const response = await fetch("/api/review?limit=50");

  if (!response.ok) {
    throw new Error("Failed to load review queue");
  }

  return response.json();
}

export async function getReviewStats(): Promise<ReviewQueueStats> {
  const response = await fetch("/api/review/stats");

  if (!response.ok) {
    throw new Error("Failed to load review stats");
  }

  return response.json();
}

export async function correctClassification(
  classificationId: number,
  identity: string,
): Promise<void> {
  const response = await fetch(
    `/api/classifications/${classificationId}/correct`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        identity,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to correct classification");
  }
}