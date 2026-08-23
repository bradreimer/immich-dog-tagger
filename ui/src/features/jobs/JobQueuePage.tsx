import { useCallback, useEffect, useMemo, useState } from "react";

import { cancelJob, clearJobHistory, getDiagnostics, getJobs } from "../../lib/api";
import { jobBadgeClassName, jobCardClassName } from "../../lib/statusColors";
import type { JobOperation, PipelineJob } from "../../types/jobs";
import type { Diagnostics } from "../../types/diagnostics";
import { IconAlertTriangle, IconLoader2, IconPlayerStop, IconRefresh, IconTrash } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

// Mirrors CANCELABLE_WHILE_RUNNING in services/jobs.py -- these are the
// only operations with an incremental commit checkpoint to roll back to
// (issue #111), so they're the only ones whose Cancel button works once
// already running. Keep in sync with the backend list.
const CANCELABLE_WHILE_RUNNING = new Set<JobOperation>([
  "scan",
  "detect",
  "classify",
  "full_pipeline",
]);

function canCancel(job: PipelineJob): boolean {
  if (job.status === "pending") {
    return true;
  }

  return job.status === "running" && CANCELABLE_WHILE_RUNNING.has(job.operation);
}

function formatOperation(operation: string): string {
  return operation
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTime(value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function progressLabel(job: PipelineJob): string {
  if (job.progress_total === null) {
    return `${job.progress_current}`;
  }

  return `${job.progress_current}/${job.progress_total}`;
}

function JobRow({
  job,
  canceling,
  onCancel,
}: {
  job: PipelineJob;
  canceling: boolean;
  onCancel: (id: number) => void;
}) {
  const hasProgressBar = job.progress_total !== null && job.progress_total > 0;
  const progressPercent = hasProgressBar
    ? (job.progress_current / job.progress_total!) * 100
    : 0;

  const isCanceling = job.status === "running" && job.cancel_requested;

  return (
    <div className={`rounded-md border p-3 ${jobCardClassName(job.status)}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">
          #{job.id} {formatOperation(job.operation)}
        </div>

        <div className="flex items-center gap-2">
          <Badge className={jobBadgeClassName(job.status)}>{job.status}</Badge>
          <span className="text-xs text-muted-foreground">{progressLabel(job)}</span>

          {isCanceling ? (
            <Button variant="outline" size="sm" disabled aria-label="Canceling">
              <IconLoader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Canceling…
            </Button>
          ) : (
            canCancel(job) && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => onCancel(job.id)}
                disabled={canceling}
                aria-label={`Cancel job #${job.id}`}
              >
                <IconPlayerStop className="h-4 w-4" aria-hidden="true" />
                Cancel
              </Button>
            )
          )}
        </div>
      </div>

      {hasProgressBar && <Progress value={progressPercent} className="mt-2" />}

      <div className="mt-2 text-sm text-muted-foreground">{job.progress_message ?? "No progress details"}</div>

      {job.error_message && (
        <div className="mt-2 text-sm text-destructive">Error: {job.error_message}</div>
      )}

      <div className="mt-2 text-xs text-muted-foreground">
        Created: {formatTime(job.created_at)} | Started: {formatTime(job.started_at)} | Completed: {formatTime(job.completed_at)}
      </div>
    </div>
  );
}

export function JobQueuePage() {
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [cancelingIds, setCancelingIds] = useState<Set<number>>(new Set());

  const load = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;
    if (!silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const [jobItems, diagData] = await Promise.all([
        getJobs(100),
        getDiagnostics().catch(() => null),
      ]);
      setJobs(jobItems);
      setDiagnostics(diagData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const groups = useMemo(() => {
    const running = jobs.filter((job) => job.status === "running");
    const pending = jobs.filter((job) => job.status === "pending");
    const history = jobs.filter((job) =>
      ["completed", "failed", "canceled"].includes(job.status),
    );

    return {
      running,
      pending,
      history,
    };
  }, [jobs]);

  const clearVisibleHistory = useCallback(async () => {
    if (groups.history.length === 0) {
      return;
    }

    setError(null);
    setClearing(true);

    try {
      await clearJobHistory();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear job history");
    } finally {
      setClearing(false);
    }
  }, [groups.history, load]);

  const handleCancel = useCallback(
    async (id: number) => {
      setError(null);
      setCancelingIds((prev) => new Set(prev).add(id));

      try {
        await cancelJob(id);
        await load({ silent: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to cancel job");
      } finally {
        setCancelingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [load],
  );

  const hasActiveJobs = groups.running.length + groups.pending.length > 0;

  useEffect(() => {
    if (!hasActiveJobs) {
      return;
    }

    const timer = window.setInterval(() => {
      void load({ silent: true });
    }, 3000);

    return () => window.clearInterval(timer);
  }, [hasActiveJobs, load]);

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Job Queue</h1>
          <p className="text-muted-foreground">Running, pending, and historical pipeline operations.</p>
          {hasActiveJobs && (
            <p className="text-xs text-muted-foreground">Live updates every 3 seconds while jobs are active.</p>
          )}
        </div>

        <Button variant="outline" onClick={() => load()} disabled={loading}>
          <IconRefresh className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </header>

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>Job Queue Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      )}

      {diagnostics && diagnostics.jobs.recent_failures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <IconAlertTriangle className="h-4 w-4 text-status-critical" aria-hidden="true" />
              Recent Failures
            </CardTitle>
            <CardDescription>The last {diagnostics.jobs.recent_failures.length} failed jobs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {diagnostics.jobs.recent_failures.map((f) => (
              <div key={f.id} className="rounded-md border border-status-critical/20 bg-status-critical/5 p-2 text-xs">
                <span className="font-medium">#{f.id} {formatOperation(f.operation)}</span>
                {f.error_message && <span className="ml-2 text-muted-foreground">{f.error_message}</span>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Running
            {groups.running.length > 0 && (
              <IconLoader2
                className="h-4 w-4 animate-spin text-muted-foreground"
                aria-hidden="true"
              />
            )}
          </CardTitle>
          <CardDescription>{groups.running.length} active jobs</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {groups.running.length === 0 ? (
            <p className="text-sm text-muted-foreground">No running jobs.</p>
          ) : (
            groups.running.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                canceling={cancelingIds.has(job.id)}
                onCancel={handleCancel}
              />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pending</CardTitle>
          <CardDescription>{groups.pending.length} queued jobs</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {groups.pending.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pending jobs.</p>
          ) : (
            groups.pending.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                canceling={cancelingIds.has(job.id)}
                onCancel={handleCancel}
              />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <CardTitle>History</CardTitle>
            <CardDescription>Completed, failed, and canceled jobs.</CardDescription>
          </div>

          <Button variant="outline" size="sm" onClick={clearVisibleHistory} disabled={groups.history.length === 0 || clearing}>
            <IconTrash className="h-4 w-4" aria-hidden="true" />
            Clear list
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {groups.history.length === 0 ? (
            <p className="text-sm text-muted-foreground">No job history yet.</p>
          ) : (
            groups.history.map((job) => (
              <JobRow key={job.id} job={job} canceling={false} onCancel={handleCancel} />
            ))
          )}
        </CardContent>
      </Card>
    </section>
  );
}
