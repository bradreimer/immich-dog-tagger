export interface SchedulerStatus {
  healthy: boolean;
  ticks: number;
  errors: number;
  started_at: string | null;
  last_tick_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
}

export interface BackupStatus {
  last_backup_at: string | null;
  backup_count: number;
  has_backup: boolean;
}

export interface DerivedDataStatus {
  healthy: boolean;
  missing_downloads: number;
  missing_crops: number;
  missing_embedding_sources: number;
  total_missing: number;
}

export interface StuckJob {
  id: number;
  operation: string;
  status: string;
  created_at: string | null;
  last_activity_at: string | null;
  idle_seconds: number;
}

export interface RecentFailure {
  id: number;
  operation: string;
  error_message: string | null;
  completed_at: string | null;
}

export interface JobSummary {
  counts: Record<string, number>;
  /** How long a job may go without progress before it counts as stuck. */
  stuck_threshold_seconds: number;
  stuck: StuckJob[];
  recent_failures: RecentFailure[];
}

export interface Diagnostics {
  db: { healthy: boolean };
  scheduler: SchedulerStatus | null;
  jobs: JobSummary;
  backup: BackupStatus;
  derived_data: DerivedDataStatus;
}
