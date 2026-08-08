import { useCallback, useEffect, useMemo, useState } from "react";

import { getJobs, getReviewStats } from "../../lib/api";
import type { PipelineJob } from "../../types/jobs";
import type { ReviewQueueStats } from "../../types/review";
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

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

export function MissionControlPage() {
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [stats, setStats] = useState<ReviewQueueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [jobItems, reviewStats] = await Promise.all([
        getJobs(25),
        getReviewStats(),
      ]);

      setJobs(jobItems);
      setStats(reviewStats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mission control");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const jobSummary = useMemo(() => {
    return jobs.reduce(
      (summary, job) => {
        summary.total += 1;
        summary[job.status] = (summary[job.status] ?? 0) + 1;
        return summary;
      },
      {
        total: 0,
        pending: 0,
        running: 0,
        completed: 0,
        failed: 0,
        canceled: 0,
      },
    );
  }, [jobs]);

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Mission Control</h1>
        <p className="text-muted-foreground">
          Monitor pipeline health and recent operations.
        </p>
      </header>

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>Mission Control Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => load()}>Retry</Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Active Jobs</CardDescription>
            <CardTitle className="text-3xl">{jobSummary.pending + jobSummary.running}</CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Completed</CardDescription>
            <CardTitle className="text-3xl">{jobSummary.completed}</CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Failed</CardDescription>
            <CardTitle className="text-3xl">{jobSummary.failed}</CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Review Remaining</CardDescription>
            <CardTitle className="text-3xl">{stats?.remaining ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current State</CardTitle>
          <CardDescription>
            Pending: {jobSummary.pending} | Running: {jobSummary.running} | Total tracked: {jobSummary.total}
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recent Jobs</CardTitle>
            <CardDescription>Most recent pipeline operations.</CardDescription>
          </div>
          <Button variant="outline" onClick={() => load()} disabled={loading}>
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No jobs have been created yet.</p>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="rounded-md border p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium">
                      #{job.id} {formatOperation(job.operation)}
                    </div>
                    <Badge variant="outline">{job.status}</Badge>
                  </div>

                  <div className="mt-2 text-sm text-muted-foreground">
                    {job.progress_message ?? "No progress message"}
                  </div>

                  <div className="mt-2 text-xs text-muted-foreground">
                    Created: {formatTimestamp(job.created_at)} | Started: {formatTimestamp(job.started_at)} | Completed: {formatTimestamp(job.completed_at)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
