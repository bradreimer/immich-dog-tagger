import { useCallback, useEffect, useMemo, useState } from "react";

import { getJobs } from "../../lib/api";
import type { PipelineJob } from "../../types/jobs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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

function getJobRowClassName(status: PipelineJob["status"]): string {
  switch (status) {
    case "running":
      return "border-sky-500/40 bg-sky-500/5 hover:bg-sky-500/10";
    case "completed":
      return "border-emerald-500/40 bg-emerald-500/5 hover:bg-emerald-500/10";
    case "failed":
      return "border-rose-500/40 bg-rose-500/5 hover:bg-rose-500/10";
    case "pending":
      return "border-amber-500/40 bg-amber-500/5 hover:bg-amber-500/10";
    case "canceled":
      return "border-zinc-500/40 bg-zinc-500/5 hover:bg-zinc-500/10";
    default:
      return "";
  }
}

function getJobBadgeClassName(status: PipelineJob["status"]): string {
  switch (status) {
    case "running":
      return "border-sky-500/40 bg-sky-500 text-sky-950";
    case "completed":
      return "border-emerald-500/40 bg-emerald-500 text-emerald-950";
    case "failed":
      return "border-rose-500/40 bg-rose-500 text-rose-950";
    case "pending":
      return "border-amber-500/40 bg-amber-500 text-amber-950";
    case "canceled":
      return "border-zinc-500/40 bg-zinc-500 text-zinc-950";
    default:
      return "";
  }
}

function JobRow({ job }: { job: PipelineJob }) {
  return (
    <div className={`rounded-md border p-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${getJobRowClassName(job.status)}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">
          #{job.id} {formatOperation(job.operation)}
        </div>

        <div className="flex items-center gap-2">
          <Badge className={getJobBadgeClassName(job.status)}>{job.status}</Badge>
          <span className="text-xs text-muted-foreground">{progressLabel(job)}</span>
        </div>
      </div>

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;

    if (!silent) {
      setLoading(true);
    }

    setError(null);

    try {
      setJobs(await getJobs(100));
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

      <Card>
        <CardHeader>
          <CardTitle>Running</CardTitle>
          <CardDescription>{groups.running.length} active jobs</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {groups.running.length === 0 ? (
            <p className="text-sm text-muted-foreground">No running jobs.</p>
          ) : (
            groups.running.map((job) => <JobRow key={job.id} job={job} />)
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
            groups.pending.map((job) => <JobRow key={job.id} job={job} />)
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
          <CardDescription>Completed, failed, and canceled jobs.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {groups.history.length === 0 ? (
            <p className="text-sm text-muted-foreground">No job history yet.</p>
          ) : (
            groups.history.map((job) => <JobRow key={job.id} job={job} />)
          )}
        </CardContent>
      </Card>
    </section>
  );
}
