import { useCallback, useEffect, useMemo, useState } from "react";

import { createJob, createSchedule, disableSchedule, enableSchedule, getDiagnostics, getJobs, getReviewStats, getSchedules, runScheduleNow } from "../../lib/api";
import type { JobOperation } from "../../types/jobs";
import type { PipelineJob } from "../../types/jobs";
import type { ReviewQueueStats } from "../../types/review";
import type { PipelineSchedule } from "../../types/schedules";
import type { Diagnostics } from "../../types/diagnostics";
import { IconBook2, IconCloudUpload, IconRocket } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DogManagementCard } from "./components/DogManagementCard";

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

function getJobCardClassName(status: PipelineJob["status"]): string {
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
    label: string;
    headline: string;
    description: string;
    icon: typeof IconRocket;
    ariaLabel: string;
  }> = [
    {
      operation: "full_pipeline",
      label: "Full Pipeline",
      headline: "Process new photos from end to end",
      description:
        "Use this after new Immich photos arrive and you want Dog Tagger to scan, detect, crop, embed, and classify them in one pass.",
      icon: IconRocket,
      ariaLabel: "Run the full pipeline",
    },
    {
      operation: "learn",
      label: "Learn",
      headline: "Add confirmed dog examples",
      description:
        "Use this after you have reviewed or curated new example images and want those confirmations to improve future classification.",
      icon: IconBook2,
      ariaLabel: "Learn from reference examples",
    },
    {
      operation: "sync",
      label: "Sync",
      headline: "Publish confident labels back to Immich",
      description:
        "Use this when the current classifications look good and you want to write those confident identities into Immich albums.",
      icon: IconCloudUpload,
      ariaLabel: "Synchronize confident labels to Immich",
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

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Mission Control</h1>
          <p className="text-muted-foreground">
            Monitor pipeline health and recent operations.
          </p>
        </div>
        <div className="self-start sm:self-auto">
          <Button
            variant="outline"
            onClick={() => {
              window.history.pushState({}, "", "/jobs");
              window.dispatchEvent(new PopStateEvent("popstate"));
            }}
          >
            Open Job Queue
          </Button>
        </div>
      </header>

      <Card className="overflow-hidden border-primary/20 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_40%),linear-gradient(135deg,_rgba(255,255,255,0.95),_rgba(254,242,242,0.88))] dark:bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.2),_transparent_40%),linear-gradient(135deg,_rgba(17,24,39,0.95),_rgba(31,41,55,0.92))]">
        <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-primary">Local dog recognition</p>
            <h2 className="text-2xl font-semibold tracking-tight">Keep your Immich library organized with a little more personality.</h2>
            <p className="text-sm text-muted-foreground">
              Run the pipeline, review results, and publish confident labels back to Immich from one place.
            </p>
          </div>
          <div className="flex shrink-0 items-center justify-center self-center rounded-2xl border border-black/10 bg-white/70 p-3 shadow-sm backdrop-blur dark:border-white/10 dark:bg-black/20 sm:self-auto">
            <img
              src="/logo_on_white.png"
              alt="Immich Dog Tagger logo"
              className="h-14 w-auto max-w-[140px] object-contain dark:hidden sm:h-16 sm:max-w-[180px]"
            />
            <img
              src="/logo_on_black.png"
              alt="Immich Dog Tagger logo"
              className="hidden h-14 w-auto max-w-[140px] object-contain dark:block sm:h-16 sm:max-w-[180px]"
            />
          </div>
        </CardContent>
      </Card>

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
                <p className={`mt-1 font-medium ${diagnostics.db.healthy ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                  {diagnostics.db.healthy ? "Healthy" : "Unhealthy"}
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Scheduler</p>
                {diagnostics.scheduler ? (
                  <p className={`mt-1 font-medium ${diagnostics.scheduler.healthy ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                    {diagnostics.scheduler.healthy ? `Healthy · ${diagnostics.scheduler.ticks} tick(s)` : `Unhealthy · ${diagnostics.scheduler.errors} error(s)`}
                  </p>
                ) : (
                  <p className="mt-1 font-medium text-muted-foreground">Not running</p>
                )}
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Last Backup</p>
                <p className={`mt-1 font-medium ${diagnostics.backup.has_backup ? "text-foreground" : "text-amber-600 dark:text-amber-400"}`}>
                  {diagnostics.backup.last_backup_at
                    ? new Date(diagnostics.backup.last_backup_at).toLocaleString()
                    : "No backup found"}
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Derived Data</p>
                <p className={`mt-1 font-medium ${diagnostics.derived_data.healthy ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                  {diagnostics.derived_data.healthy
                    ? "All present"
                    : `${diagnostics.derived_data.total_missing} missing`}
                </p>
              </div>
            </div>

            {diagnostics.jobs.stuck.length > 0 && (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3">
                <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
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
                  <div key={f.id} className="rounded-md border border-rose-500/20 bg-rose-500/5 p-2 text-xs">
                    <span className="font-medium">#{f.id} {f.operation}</span>
                    {f.error_message && <span className="ml-2 text-muted-foreground">{f.error_message}</span>}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <DogManagementCard />

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
              <div key={item.operation} className="rounded-md border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:ring-1 hover:ring-foreground/20">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="font-medium">{item.headline}</div>
                    <Badge variant="outline">{item.label}</Badge>
                  </div>

                  <Button
                    aria-label={item.ariaLabel}
                    title={item.ariaLabel}
                    variant={item.operation === "full_pipeline" ? "default" : "outline"}
                    size="icon"
                    className="h-11 w-11 shrink-0 rounded-full"
                    disabled={launching !== null}
                    onClick={() => launchOperation(item.operation)}
                  >
                    <item.icon className="h-5 w-5" aria-hidden="true" />
                  </Button>
                </div>

                <p className="mt-3 text-sm text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </div>

          {actionMessage && <p className="text-sm text-emerald-700 dark:text-emerald-300">{actionMessage}</p>}
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
              {operations.map((item) => (
                <option key={item.operation} value={item.operation}>{item.label}</option>
              ))}
            </select>
            <input
              className="rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="Cron expression"
              value={scheduleForm.expression}
              onChange={(event) => setScheduleForm((current) => ({ ...current, expression: event.target.value }))}
            />
            <button
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
              disabled={scheduleBusy || !scheduleForm.name}
              onClick={() => void handleCreateSchedule()}
            >
              {scheduleBusy ? "Saving..." : "Create"}
            </button>
          </div>

          {scheduleMessage && <p className="text-sm text-emerald-700 dark:text-emerald-300">{scheduleMessage}</p>}
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
                      {schedule.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void runSchedule(schedule)}>
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
                  className={`rounded-md border p-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${getJobCardClassName(job.status)}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium">
                      #{job.id} {formatOperation(job.operation)}
                    </div>
                    <Badge className={getJobBadgeClassName(job.status)}>{job.status}</Badge>
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
