import { useCallback, useEffect, useMemo, useState } from "react";

import { createJob, createSchedule, disableSchedule, enableSchedule, getDiagnostics, getJobs, getReviewStats, getSchedules, runScheduleNow } from "../../lib/api";
import { jobBadgeClassName, jobCardClassName, jobTextClassName } from "../../lib/statusColors";
import { formatRelativeTime } from "../../lib/utils";
import type { JobOperation } from "../../types/jobs";
import type { PipelineJob } from "../../types/jobs";
import type { ReviewQueueStats } from "../../types/review";
import type { PipelineSchedule } from "../../types/schedules";
import type { Diagnostics } from "../../types/diagnostics";
import {
  IconActivity,
  IconAlertTriangle,
  IconArrowRight,
  IconCircleCheck,
  IconClipboardList,
  IconCloudUpload,
  IconListDetails,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlus,
  IconRefresh,
  IconRefreshDot,
  IconRocket,
  IconSparkles,
} from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";

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
  const [schedules, setSchedules] = useState<PipelineSchedule[]>([]);
  const [stats, setStats] = useState<ReviewQueueStats | null>(null);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [launching, setLaunching] = useState<JobOperation | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [scheduleForm, setScheduleForm] = useState({
    name: "",
    operation: "full_pipeline" as JobOperation,
    expression: "0 * * * *",
    timezone_name: "UTC",
    enabled: true,
  });
  const [scheduleBusy, setScheduleBusy] = useState(false);
  const [scheduleMessage, setScheduleMessage] = useState<string | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

  const operations: Array<{
    operation: JobOperation;
    headline: string;
    actionLabel: string;
    description: string;
    icon: typeof IconRocket;
    ariaLabel: string;
  }> = [
    {
      operation: "full_pipeline",
      headline: "Process new photos",
      actionLabel: "Run",
      description:
        "Use this after new Immich photos arrive to make Dog Tagger scan, detect, crop, embed, and classify them in one pass.",
      icon: IconRocket,
      ariaLabel: "Run the full pipeline",
    },
    {
      operation: "reclassify",
      headline: "Reclassify with reviewed examples",
      actionLabel: "Reclassify",
      description:
        "Recompute predictions for existing photos using everything you've reviewed so far. It never rescans, redownloads, or redetects, and it never changes a label you've already confirmed.",
      icon: IconRefreshDot,
      ariaLabel: "Reclassify existing photos with reviewed examples",
    },
    {
      operation: "sync",
      headline: "Publish labels back to Immich",
      actionLabel: "Sync",
      description:
        "Use this when the current classifications look good and you want to write those identities into Immich albums.",
      icon: IconCloudUpload,
      ariaLabel: "Synchronize album to Immich",
    },
  ];

  const load = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;
    if (!silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const [jobItems, reviewStats, scheduleItems, diagData] = await Promise.all([
        getJobs(25),
        getReviewStats(),
        getSchedules(),
        getDiagnostics().catch(() => null),
      ]);

      setJobs(jobItems);
      setStats(reviewStats);
      setSchedules(scheduleItems);
      setDiagnostics(diagData);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mission control");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const launchOperation = useCallback(
    async (operation: JobOperation) => {
      setActionError(null);
      setActionMessage(null);
      setLaunching(operation);

      try {
        const job = await createJob(operation);
        setActionMessage(`Queued job #${job.id} (${formatOperation(job.operation)}).`);
        await load();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Failed to start operation");
      } finally {
        setLaunching(null);
      }
    },
    [load],
  );

  const handleCreateSchedule = useCallback(async () => {
    setScheduleError(null);
    setScheduleMessage(null);
    setScheduleBusy(true);

    try {
      const created = await createSchedule(scheduleForm);
      setSchedules((current) => [created, ...current]);
      setScheduleMessage(`Created schedule “${created.name}”.`);
      setScheduleForm({
        name: "",
        operation: "full_pipeline",
        expression: "0 * * * *",
        timezone_name: "UTC",
        enabled: true,
      });
      await load({ silent: true });
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : "Failed to create schedule");
    } finally {
      setScheduleBusy(false);
    }
  }, [load, scheduleForm]);

  const toggleSchedule = useCallback(async (schedule: PipelineSchedule, enabled: boolean) => {
    try {
      const updated = enabled
        ? await enableSchedule(schedule.id)
        : await disableSchedule(schedule.id);
      setSchedules((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : "Failed to update schedule");
    }
  }, []);

  const runSchedule = useCallback(async (schedule: PipelineSchedule) => {
    try {
      const job = await runScheduleNow(schedule.id);
      setScheduleMessage(`Triggered job #${job.id} for “${schedule.name}”.`);
      await load({ silent: true });
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : "Failed to run schedule");
    }
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

  const hasActiveJobs = jobSummary.pending + jobSummary.running > 0;

  useEffect(() => {
    if (!hasActiveJobs) {
      return;
    }

    const timer = window.setInterval(() => {
      void load({ silent: true });
    }, 3000);

    return () => window.clearInterval(timer);
  }, [hasActiveJobs, load]);

  // Forces a re-render every 30s so the relative "last updated" text stays accurate
  // even when nothing else on the page is refreshing.
  const [, forceRelativeTimeUpdate] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => forceRelativeTimeUpdate((n) => n + 1), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Mission Control</h1>
          <p className="text-muted-foreground">
            Overview of pipeline health and classification progress.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            disabled={launching !== null}
            onClick={() => launchOperation("reclassify")}
          >
            <IconRefreshDot className="h-4 w-4" aria-hidden="true" />
            Reclassify
          </Button>
          <Button disabled={launching !== null} onClick={() => launchOperation("full_pipeline")}>
            <IconRocket className="h-4 w-4" aria-hidden="true" />
            Run Pipeline
          </Button>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span title={lastUpdated?.toLocaleTimeString()}>
              {lastUpdated ? `Last updated: ${formatRelativeTime(lastUpdated)}` : "Loading…"}
            </span>
            <button
              type="button"
              aria-label="Refresh dashboard"
              title="Refresh dashboard"
              className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
              onClick={() => load()}
              disabled={loading}
            >
              <IconRefresh className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>Mission Control Error</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => load()}>
              <IconRefresh className="h-4 w-4" aria-hidden="true" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          icon={IconActivity}
          tone="info"
          label="Active Jobs"
          value={jobSummary.pending + jobSummary.running}
          subtext={`${jobSummary.running} running, ${jobSummary.pending} pending`}
        />
        <StatTile
          icon={IconCircleCheck}
          tone="good"
          label="Completed"
          value={jobSummary.completed}
          subtext={`of ${jobSummary.total} tracked jobs`}
        />
        <StatTile
          icon={IconAlertTriangle}
          tone="critical"
          label="Failed"
          value={jobSummary.failed}
          subtext={jobSummary.failed > 0 ? "may need attention" : "none right now"}
        />
        <StatTile
          icon={IconClipboardList}
          tone="warning"
          label="Review Remaining"
          value={stats?.remaining ?? 0}
          subtext={stats ? `${stats.reviewed} of ${stats.total} reviewed` : undefined}
        />
      </div>

      {stats && (
        <div
          className={
            stats.remaining > 0
              ? "flex flex-wrap items-center justify-between gap-3 rounded-lg border border-status-warning/30 bg-status-warning/5 p-4"
              : "flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/40 p-4"
          }
        >
          <div className="flex items-center gap-3">
            <IconSparkles
              className={stats.remaining > 0 ? "h-5 w-5 shrink-0 text-status-warning" : "h-5 w-5 shrink-0 text-muted-foreground"}
              aria-hidden="true"
            />
            <p className="text-sm">
              {stats.remaining > 0 ? (
                <>
                  <span className="font-medium">{stats.remaining} image{stats.remaining === 1 ? "" : "s"}</span>{" "}
                  need review. Reviewing them teaches the classifier and shrinks the queue.
                </>
              ) : (
                "All caught up -- no images need review right now."
              )}
            </p>
          </div>

          {stats.remaining > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                window.history.pushState({}, "", "/review");
                window.dispatchEvent(new PopStateEvent("popstate"));
              }}
            >
              Go to Review
              <IconArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      )}

      {diagnostics && (
        <Card>
          <CardHeader>
            <CardTitle>System Diagnostics</CardTitle>
            <CardDescription>Operational health at a glance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Database</p>
                <p className={`mt-1 font-medium ${diagnostics.db.healthy ? "text-status-good" : "text-status-critical"}`}>
                  {diagnostics.db.healthy ? "Healthy" : "Unhealthy"}
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Scheduler</p>
                {diagnostics.scheduler ? (
                  <p className={`mt-1 font-medium ${diagnostics.scheduler.healthy ? "text-status-good" : "text-status-critical"}`}>
                    {diagnostics.scheduler.healthy ? `Healthy · ${diagnostics.scheduler.ticks} tick(s)` : `Unhealthy · ${diagnostics.scheduler.errors} error(s)`}
                  </p>
                ) : (
                  <p className="mt-1 font-medium text-muted-foreground">Not running</p>
                )}
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Last Backup</p>
                <p className={`mt-1 font-medium ${diagnostics.backup.has_backup ? "text-foreground" : "text-status-warning"}`}>
                  {diagnostics.backup.last_backup_at
                    ? new Date(diagnostics.backup.last_backup_at).toLocaleString()
                    : "No backup found"}
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Derived Data</p>
                <p className={`mt-1 font-medium ${diagnostics.derived_data.healthy ? "text-status-good" : "text-status-warning"}`}>
                  {diagnostics.derived_data.healthy
                    ? "All present"
                    : `${diagnostics.derived_data.total_missing} missing`}
                </p>
              </div>
            </div>

            {diagnostics.jobs.stuck.length > 0 && (
              <div className="rounded-md border border-status-warning/40 bg-status-warning/5 p-3">
                <p className="text-sm font-medium text-status-warning">
                  {diagnostics.jobs.stuck.length} stuck job(s) — manual recovery may be required.
                </p>
                {diagnostics.jobs.stuck.map((j) => (
                  <p key={j.id} className="mt-1 text-xs text-muted-foreground">
                    #{j.id} {j.operation} ({j.status})
                  </p>
                ))}
              </div>
            )}

            {diagnostics.jobs.recent_failures.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Recent failures</p>
                {diagnostics.jobs.recent_failures.map((f) => (
                  <div key={f.id} className="rounded-md border border-status-critical/20 bg-status-critical/5 p-2 text-xs">
                    <span className="font-medium">#{f.id} {f.operation}</span>
                    {f.error_message && <span className="ml-2 text-muted-foreground">{f.error_message}</span>}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Manual Operations</CardTitle>
          <CardDescription>
            Choose the job that matches what you are trying to accomplish.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {operations.map((item) => (
              <div key={item.operation} className="rounded-md border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="font-medium">{item.headline}</div>
                  </div>

                  <Button
                    aria-label={item.ariaLabel}
                    title={item.ariaLabel}
                    variant={item.operation === "full_pipeline" ? "default" : "outline"}
                    className="h-11 shrink-0 px-4"
                    disabled={launching !== null}
                    onClick={() => launchOperation(item.operation)}
                  >
                    <item.icon className="h-5 w-5" aria-hidden="true" />
                    {item.actionLabel}
                  </Button>
                </div>

                <p className="mt-3 text-sm text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </div>

          {actionMessage && <p className="text-sm text-status-good">{actionMessage}</p>}
          {actionError && <p className="text-sm text-destructive">{actionError}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Automation Schedules</CardTitle>
          <CardDescription>Configure unattended operations and trigger them manually when needed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1.2fr_0.6fr_0.6fr_0.4fr]">
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="Schedule name"
              value={scheduleForm.name}
              onChange={(event) => setScheduleForm((current) => ({ ...current, name: event.target.value }))}
            />
            <select
              className="rounded-md border bg-background px-3 py-2 text-sm"
              value={scheduleForm.operation}
              onChange={(event) => setScheduleForm((current) => ({ ...current, operation: event.target.value as JobOperation }))}
            >
            </select>
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="Cron expression"
              value={scheduleForm.expression}
              onChange={(event) => setScheduleForm((current) => ({ ...current, expression: event.target.value }))}
            />
            <Button
              disabled={scheduleBusy || !scheduleForm.name}
              onClick={() => void handleCreateSchedule()}
            >
              <IconPlus className="h-4 w-4" aria-hidden="true" />
              {scheduleBusy ? "Saving..." : "Create"}
            </Button>
          </div>

          {scheduleMessage && <p className="text-sm text-status-good">{scheduleMessage}</p>}
          {scheduleError && <p className="text-sm text-destructive">{scheduleError}</p>}

          {schedules.length === 0 ? (
            <p className="text-sm text-muted-foreground">No schedules have been added yet.</p>
          ) : (
            <div className="space-y-3">
              {schedules.map((schedule) => (
                <div key={schedule.id} className="flex flex-col gap-3 rounded-md border p-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="font-medium">{schedule.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {formatOperation(schedule.operation)} • {schedule.expression} • {schedule.timezone_name}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Next: {formatTimestamp(schedule.next_run_at)} | Last: {formatTimestamp(schedule.last_run_at)} | Result: {schedule.last_run_result ?? "-"}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={schedule.enabled ? "default" : "secondary"}>{schedule.enabled ? "Enabled" : "Disabled"}</Badge>
                    <Button variant="outline" size="sm" onClick={() => void toggleSchedule(schedule, !schedule.enabled)}>
                      {schedule.enabled ? <IconPlayerPause className="h-4 w-4" aria-hidden="true" /> : <IconPlayerPlay className="h-4 w-4" aria-hidden="true" />}
                      {schedule.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void runSchedule(schedule)}>
                      <IconPlayerPlay className="h-4 w-4" aria-hidden="true" />
                      Run Now
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Current State</CardTitle>
          <CardDescription>
            Pending: {jobSummary.pending} | Running: {jobSummary.running} | Total tracked: {jobSummary.total}
          </CardDescription>
          {hasActiveJobs && (
            <p className="text-xs text-muted-foreground">Live updates every 3 seconds while jobs are active.</p>
          )}
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recent Jobs</CardTitle>
            <CardDescription>Most recent pipeline operations.</CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              window.history.pushState({}, "", "/jobs");
              window.dispatchEvent(new PopStateEvent("popstate"));
            }}
          >
            <IconListDetails className="h-4 w-4" aria-hidden="true" />
            View all
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
                  className={`rounded-md border p-3 ${jobCardClassName(job.status)}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium">
                      #{job.id} {formatOperation(job.operation)}
                    </div>
                    <Badge className={jobBadgeClassName(job.status)}>{job.status}</Badge>
                  </div>

                  <div className={`mt-2 text-sm ${job.status === "failed" ? jobTextClassName(job.status) : "text-muted-foreground"}`}>
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
