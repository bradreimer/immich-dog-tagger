import type { JobOperation } from "./jobs";

export interface PipelineSchedule {
  id: number;
  name: string;
  operation: JobOperation;
  expression: string;
  timezone_name: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_result: string | null;
}
