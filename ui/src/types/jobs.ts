export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "canceled";

export type JobOperation =
  | "scan"
  | "detect"
  | "embed"
  | "classify"
  | "reclassify"
  | "learn"
  | "sync"
  | "full_pipeline"
  | "reembed"
  | "look_harder";

export interface PipelineJob {
  id: number;
  operation: JobOperation;
  status: JobStatus;
  progress_current: number;
  progress_total: number | null;
  progress_message: string | null;
  error_message: string | null;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  /** The one photo a per-photo job acts on (issue #390's look_harder). */
  target_immich_asset_id?: string | null;
}
