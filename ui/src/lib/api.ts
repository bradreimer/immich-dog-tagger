import type {
  ReviewItem,
  ReviewQueueStats,
} from "../types/review";
import type { PipelineJob } from "../types/jobs";
import type { JobOperation } from "../types/jobs";
import type { PipelineSchedule } from "../types/schedules";

export type ReviewQuery = {
  unknown?: boolean;
  confidence_below?: number;
  candidate_conflict?: boolean;
};

export async function getReview(
  query: ReviewQuery = {},
): Promise<ReviewItem[]> {
  const params = new URLSearchParams();
  params.set("limit", "50");

  if (query.unknown) {
    params.set("unknown", "true");
  }

  if (query.confidence_below !== undefined) {
    params.set(
      "confidence_below",
      query.confidence_below.toString(),
    );
  }

  if (query.candidate_conflict) {
    params.set(
      "candidate_conflict",
      "true",
    );
  }

  const response = await fetch(
    `/api/review?${params.toString()}`,
  );

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

export async function getJobs(
  limit = 20,
): Promise<PipelineJob[]> {
  const response = await fetch(`/api/jobs?limit=${limit}`);

  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }

  return response.json();
}

export async function getSchedules(): Promise<PipelineSchedule[]> {
  const response = await fetch("/api/schedules");

  if (!response.ok) {
    throw new Error("Failed to load schedules");
  }

  return response.json();
}

export async function createSchedule(payload: {
  name: string;
  operation: JobOperation;
  expression: string;
  timezone_name?: string;
  enabled?: boolean;
}): Promise<PipelineSchedule> {
  const response = await fetch("/api/schedules", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to create schedule");
  }

  return response.json();
}

export async function updateSchedule(
  scheduleId: number,
  payload: Partial<PipelineSchedule>,
): Promise<PipelineSchedule> {
  const response = await fetch(`/api/schedules/${scheduleId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to update schedule");
  }

  return response.json();
}

export async function enableSchedule(scheduleId: number): Promise<PipelineSchedule> {
  const response = await fetch(`/api/schedules/${scheduleId}/enable`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to enable schedule");
  }

  return response.json();
}

export async function disableSchedule(scheduleId: number): Promise<PipelineSchedule> {
  const response = await fetch(`/api/schedules/${scheduleId}/disable`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to disable schedule");
  }

  return response.json();
}

export async function runScheduleNow(scheduleId: number): Promise<PipelineJob> {
  const response = await fetch(`/api/schedules/${scheduleId}/run-now`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to run schedule now");
  }

  return response.json();
}

export async function createJob(
  operation: JobOperation,
): Promise<PipelineJob> {
  const response = await fetch("/api/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      operation,
      start: true,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to create job");
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

export async function skipClassification(
  classificationId: number,
): Promise<void> {
  const response = await fetch(
    `/api/review/${classificationId}/skip`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error("Failed to skip classification");
  }
}