import type {
  ReviewItem,
  ReviewQueueStats,
} from "../types/review";
import type { Dog, DogMergeResult, Species } from "../types/dogs";
import type { PipelineJob } from "../types/jobs";
import type { JobOperation } from "../types/jobs";
import type { PipelineSchedule } from "../types/schedules";
import type { Diagnostics } from "../types/diagnostics";
import type { LearningMetrics } from "../types/metrics";
import type { LibraryPage, LibrarySort } from "../types/library";
import type {
  ClusterApprovalResult,
  ClusterProposal,
  ClusterSort,
} from "../types/clusters";
import type { Settings, TaggingSensitivity } from "../types/settings";
import type { Health } from "../types/health";
import type {
  InsightCard,
  InsightsSummary,
  PersonCount,
  PlaceCount,
  TopPhoto,
} from "../types/insights";
import type { PhotoLookupResult } from "../types/photoLookup";

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

export type LibraryQuery = {
  identity?: string;
  species?: string;
  reviewed?: boolean;
  captured_after?: string;
  captured_before?: string;
  sort?: LibrarySort;
  limit?: number;
  offset?: number;
};

export async function getLibrary(
  query: LibraryQuery = {},
): Promise<LibraryPage> {
  const params = new URLSearchParams();

  if (query.identity) {
    params.set("identity", query.identity);
  }

  if (query.species) {
    params.set("species", query.species);
  }

  if (query.reviewed !== undefined) {
    params.set("reviewed", String(query.reviewed));
  }

  if (query.captured_after) {
    params.set("captured_after", query.captured_after);
  }

  if (query.captured_before) {
    params.set("captured_before", query.captured_before);
  }

  if (query.sort) {
    params.set("sort", query.sort);
  }

  params.set("limit", String(query.limit ?? 50));
  params.set("offset", String(query.offset ?? 0));

  const response = await fetch(`/api/library?${params.toString()}`);

  if (!response.ok) {
    throw new Error("Failed to load library");
  }

  return response.json();
}

/**
 * One classification by id, in the same shape a review-queue item has
 * (v1.11) -- lets the Review page open any photo, not only one already in
 * the active queue (e.g. from the Library's Edit link).
 */
export async function getClassification(
  classificationId: number,
): Promise<ReviewItem> {
  const response = await fetch(`/api/classifications/${classificationId}`);

  if (response.status === 404) {
    throw new ClassificationNotFoundError(
      `Classification ${classificationId} not found`,
    );
  }

  if (!response.ok) {
    throw new Error("Failed to load classification");
  }

  return response.json();
}

/** Thrown by getClassification() when the id doesn't exist. */
export class ClassificationNotFoundError extends Error {}

export async function getReviewStats(): Promise<ReviewQueueStats> {
  const response = await fetch("/api/review/stats");

  if (!response.ok) {
    throw new Error("Failed to load review stats");
  }

  return response.json();
}

export async function getDogs(options: { includeInactive?: boolean } = {}): Promise<Dog[]> {
  const params = new URLSearchParams();

  if (options.includeInactive === false) {
    params.set("include_inactive", "false");
  }

  const query = params.toString();
  const response = await fetch(query ? `/api/dogs?${query}` : "/api/dogs");

  if (!response.ok) {
    throw new Error("Failed to load dogs");
  }

  return response.json();
}

export async function createDog(name: string, species: Species = "dog"): Promise<Dog> {
  const response = await fetch("/api/dogs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name, species }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to create dog");
  }

  return response.json();
}

export async function renameDog(id: number, name: string): Promise<Dog> {
  const response = await fetch(`/api/dogs/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to update dog");
  }

  return response.json();
}

export async function activateDog(id: number): Promise<Dog> {
  const response = await fetch(`/api/dogs/${id}/activate`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to activate dog");
  }

  return response.json();
}

export async function deactivateDog(id: number): Promise<Dog> {
  const response = await fetch(`/api/dogs/${id}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("Failed to deactivate dog");
  }

  return response.json();
}

export async function mergeDogs(sourceId: number, targetId: number): Promise<DogMergeResult> {
  const response = await fetch(`/api/dogs/${sourceId}/merge`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ target_id: targetId }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to merge identities");
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

export async function clearJobHistory(): Promise<{ cleared: number }> {
  const response = await fetch("/api/jobs/clear-history", {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to clear job history");
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

export async function cancelJob(id: number): Promise<PipelineJob> {
  const response = await fetch(`/api/jobs/${id}/cancel`, {
    method: "POST",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : "Failed to cancel job");
  }

  return response.json();
}

/**
 * The pending recommendations for one pet, grouped into clusters of visually
 * similar crops. A read -- nothing is assigned until a cluster is approved.
 */
export async function getPetClusters(
  identity: string,
  species: string,
  sort?: ClusterSort,
): Promise<ClusterProposal> {
  const params = new URLSearchParams();
  params.set("identity", identity);
  params.set("species", species);

  if (sort) {
    params.set("sort", sort);
  }

  const response = await fetch(`/api/library/clusters?${params.toString()}`);

  if (!response.ok) {
    throw new Error("Failed to load recommendations");
  }

  return response.json();
}

/**
 * One pet's already-confirmed photos (v1.10), grouped into clusters of
 * visually similar crops -- the confirmed-photo counterpart of
 * `getPetClusters`. A read: nothing is moved until a selection is moved.
 */
export async function getConfirmedClusters(
  identity: string,
  species: string,
  sort?: ClusterSort,
): Promise<ClusterProposal> {
  const params = new URLSearchParams();
  params.set("identity", identity);
  params.set("species", species);

  if (sort) {
    params.set("sort", sort);
  }

  const response = await fetch(`/api/library/clusters/confirmed?${params.toString()}`);

  if (!response.ok) {
    throw new Error("Failed to load confirmed photos");
  }

  return response.json();
}

/**
 * Move a selection of `sourceIdentity`'s already-confirmed photos to
 * `targetIdentity` (v1.10) -- the bulk form of the Library's existing
 * per-photo "Correct to..." control.
 */
export async function moveConfirmedPhotos(
  sourceIdentity: string,
  targetIdentity: string,
  species: string,
  classificationIds: number[],
): Promise<ClusterApprovalResult> {
  const response = await fetch("/api/library/clusters/move", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source_identity: sourceIdentity,
      target_identity: targetIdentity,
      species,
      classification_ids: classificationIds,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to move photos");
  }

  return response.json();
}

/** Assign a pet's identity to every listed photo, as one action. */
export async function approveCluster(
  identity: string,
  species: string,
  classificationIds: number[],
): Promise<ClusterApprovalResult> {
  const response = await fetch("/api/library/clusters/approve", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      identity,
      species,
      classification_ids: classificationIds,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to approve cluster");
  }

  return response.json();
}

/**
 * Assign a *different* pet's identity to every listed photo (issue #166).
 *
 * Same request/response shape as `approveCluster`, but the server does not
 * require the classifier to have proposed this pet for these crops --
 * reassigning to a pet the classifier never put forward for a
 * correctly-clustered group is the point of this action.
 */
export async function reassignCluster(
  identity: string,
  species: string,
  classificationIds: number[],
): Promise<ClusterApprovalResult> {
  const response = await fetch("/api/library/clusters/reassign", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      identity,
      species,
      classification_ids: classificationIds,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to reassign cluster");
  }

  return response.json();
}

/**
 * Record that every listed photo is *not* this pet (issue #144).
 *
 * Settles no identity: each photo is rescored without the rejected pet
 * and stays pending, so the owner can say who an animal is not without
 * having to say who it is.
 */
export async function rejectCluster(
  identity: string,
  species: string,
  classificationIds: number[],
): Promise<ClusterApprovalResult> {
  const response = await fetch("/api/library/clusters/reject", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      identity,
      species,
      classification_ids: classificationIds,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to reject cluster");
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

export async function correctSpecies(
  classificationId: number,
  species: "dog" | "cat",
): Promise<ReviewItem> {
  const response = await fetch(
    `/api/classifications/${classificationId}/species`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        species,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to correct species");
  }

  return response.json();
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

export async function getDiagnostics(): Promise<Diagnostics> {
  const response = await fetch("/api/diagnostics");
  if (!response.ok) {
    throw new Error("Failed to load diagnostics");
  }
  return response.json();
}

export async function getLearningMetrics(): Promise<LearningMetrics> {
  const response = await fetch("/api/metrics");
  if (!response.ok) {
    throw new Error("Failed to load learning metrics");
  }
  return response.json();
}

export async function getSettings(): Promise<Settings> {
  const response = await fetch("/api/settings");
  if (!response.ok) {
    throw new Error("Failed to load settings");
  }
  return response.json();
}

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error("Failed to load health");
  }
  return response.json();
}

export async function getInsightsSummary(identityId: number): Promise<InsightsSummary> {
  const response = await fetch(`/api/dogs/${identityId}/insights/summary`);
  if (!response.ok) {
    throw new Error("Failed to load insights summary");
  }
  return response.json();
}

export async function getInsightsPlaces(identityId: number): Promise<PlaceCount[]> {
  const response = await fetch(`/api/dogs/${identityId}/insights/places`);
  if (!response.ok) {
    throw new Error("Failed to load places");
  }
  return response.json();
}

export async function getInsightsPeople(identityId: number): Promise<PersonCount[]> {
  const response = await fetch(`/api/dogs/${identityId}/insights/people`);
  if (!response.ok) {
    throw new Error("Failed to load people");
  }
  return response.json();
}

export async function getInsightsCards(identityId: number): Promise<InsightCard[]> {
  const response = await fetch(`/api/dogs/${identityId}/insights/cards`);
  if (!response.ok) {
    throw new Error("Failed to load insight cards");
  }
  return response.json();
}

export async function getInsightsTopPhotos(
  identityId: number,
  limit = 10,
): Promise<TopPhoto[]> {
  const response = await fetch(`/api/dogs/${identityId}/insights/top-photos?limit=${limit}`);
  if (!response.ok) {
    throw new Error("Failed to load top photos");
  }
  return response.json();
}
/** Thrown by getPhotoLookup() when the pasted photo hasn't been scanned by this instance. */
export class PhotoLookupNotFoundError extends Error {}

/**
 * Look up what this instance knows about an Immich photo by its asset id
 * (issue #179) -- the detections/identities/confidences shown for a pasted
 * Immich link.
 */
export async function getPhotoLookup(
  immichAssetId: string,
): Promise<PhotoLookupResult> {
  const response = await fetch(
    `/api/photo-lookup/${encodeURIComponent(immichAssetId)}`,
  );

  if (response.status === 404) {
    throw new PhotoLookupNotFoundError(
      "That photo hasn't been scanned by this instance yet.",
    );
  }

  if (!response.ok) {
    throw new Error("Failed to look up photo");
  }

  return response.json();
}

/** Flag a Photo Lookup box as not a dog or cat (issue #185). Reversible via unmarkCropNotAnimal(). */
export async function markCropNotAnimal(cropId: number): Promise<void> {
  const response = await fetch(`/api/crops/${cropId}/not-animal`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to mark detection as not a dog or cat");
  }
}

/** Undo markCropNotAnimal(). */
export async function unmarkCropNotAnimal(cropId: number): Promise<void> {
  const response = await fetch(`/api/crops/${cropId}/not-animal`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("Failed to undo not-a-dog-or-cat mark");
  }
}

/** Change how cautious automatic tagging is (issue #149). */
export async function setTaggingSensitivity(
  sensitivity: TaggingSensitivity,
): Promise<Settings> {
  const response = await fetch("/api/settings/tagging-sensitivity", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tagging_sensitivity: sensitivity }),
  });

  if (!response.ok) {
    throw new Error("Failed to update tagging sensitivity");
  }

  return response.json();
}
