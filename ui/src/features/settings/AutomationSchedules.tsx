import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createSchedule,
  getSchedules,
  runScheduleNow,
  updateSchedule,
} from "../../lib/api";
import type { JobOperation } from "../../types/jobs";
import type { PipelineSchedule } from "../../types/schedules";
import {
  IconChevronDown,
  IconCloudUpload,
  IconExternalLink,
  IconPlayerPlay,
  IconRefreshDot,
  IconRocket,
  IconSchool,
} from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Switch } from "@/components/ui/switch";

const DEFAULT_EXPRESSION = "0 * * * *";

type AutomationOperation = {
  operation: JobOperation;
  title: string;
  description: string;
  toggleLabel: string;
  icon: typeof IconRocket;
};

const AUTOMATION_OPERATIONS: AutomationOperation[] = [
  {
    operation: "full_pipeline",
    title: "Process new photos",
    description:
      "Use this after new Immich photos arrive to make Dog Tagger scan, detect, crop, embed, and classify them in one pass.",
    toggleLabel: "Enable automatic processing of new photos",
    icon: IconRocket,
  },
  {
    operation: "reclassify",
    title: "Reclassify with reviewed examples",
    description:
      "Recompute predictions for existing photos using everything you've reviewed so far. It never rescans, redownloads, or redetects, and it never changes a label you've already confirmed.",
    toggleLabel: "Enable automatic reclassification",
    icon: IconRefreshDot,
  },
  {
    operation: "learn",
    title: "Learn from reviewed examples",
    description:
      "Fold recent review corrections into the reference set the classifier uses for future predictions.",
    toggleLabel: "Enable automatic learning",
    icon: IconSchool,
  },
  {
    operation: "sync",
    title: "Publish labels back to Immich",
    description:
      "Use this when the current classifications look good and you want to write those identities into Immich albums and tags.",
    toggleLabel: "Enable automatic sync to Immich",
    icon: IconCloudUpload,
  },
];

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

export function AutomationSchedules() {
  const [schedules, setSchedules] = useState<PipelineSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openOperation, setOpenOperation] = useState<JobOperation | null>(null);
  const [expressionDrafts, setExpressionDrafts] = useState<Partial<Record<JobOperation, string>>>({});
  const [expressionErrors, setExpressionErrors] = useState<Partial<Record<JobOperation, string>>>({});
  const [busyOperation, setBusyOperation] = useState<JobOperation | null>(null);
  const [runMessages, setRunMessages] = useState<Partial<Record<JobOperation, string>>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSchedules(await getSchedules());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load automation settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const scheduleByOperation = useMemo(() => {
    const map = new Map<JobOperation, PipelineSchedule>();
    for (const schedule of schedules) {
      if (!map.has(schedule.operation)) {
        map.set(schedule.operation, schedule);
      }
    }
    return map;
  }, [schedules]);

  const replaceSchedule = useCallback((updated: PipelineSchedule) => {
    setSchedules((current) => [...current.filter((item) => item.id !== updated.id), updated]);
  }, []);

  const expressionFor = useCallback(
    (operation: JobOperation) => {
      const draft = expressionDrafts[operation];
      if (draft !== undefined) {
        return draft;
      }
      return scheduleByOperation.get(operation)?.expression ?? DEFAULT_EXPRESSION;
    },
    [expressionDrafts, scheduleByOperation],
  );

  const ensureSchedule = useCallback(
    async (
      operation: JobOperation,
      title: string,
      overrides: { enabled?: boolean; expression?: string },
    ): Promise<PipelineSchedule> => {
      const existing = scheduleByOperation.get(operation);
      if (existing) {
        return updateSchedule(existing.id, overrides);
      }

      return createSchedule({
        name: title,
        operation,
        expression: overrides.expression ?? DEFAULT_EXPRESSION,
        enabled: overrides.enabled ?? false,
      });
    },
    [scheduleByOperation],
  );

  const handleToggle = useCallback(
    async (operation: JobOperation, title: string, checked: boolean) => {
      setBusyOperation(operation);
      setError(null);
      try {
        const updated = await ensureSchedule(operation, title, { enabled: checked });
        replaceSchedule(updated);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update schedule");
      } finally {
        setBusyOperation(null);
      }
    },
    [ensureSchedule, replaceSchedule],
  );

  const handleExpressionCommit = useCallback(
    async (operation: JobOperation, title: string) => {
      const draft = expressionDrafts[operation];
      if (draft === undefined) {
        return;
      }

      const existing = scheduleByOperation.get(operation);
      if (existing && existing.expression === draft) {
        setExpressionDrafts((current) => {
          const { [operation]: _removed, ...rest } = current;
          return rest;
        });
        return;
      }

      setExpressionErrors((current) => ({ ...current, [operation]: undefined }));
      setBusyOperation(operation);
      try {
        const updated = await ensureSchedule(operation, title, { expression: draft });
        replaceSchedule(updated);
        setExpressionDrafts((current) => {
          const { [operation]: _removed, ...rest } = current;
          return rest;
        });
      } catch (err) {
        setExpressionErrors((current) => ({
          ...current,
          [operation]: err instanceof Error ? err.message : "Invalid cron expression",
        }));
      } finally {
        setBusyOperation(null);
      }
    },
    [ensureSchedule, expressionDrafts, replaceSchedule, scheduleByOperation],
  );

  const handleRunNow = useCallback(async (schedule: PipelineSchedule) => {
    setError(null);
    try {
      const job = await runScheduleNow(schedule.id);
      setRunMessages((current) => ({ ...current, [schedule.operation]: `Queued job #${job.id}.` }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run now");
    }
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Automation</CardTitle>
        <CardDescription>
          Turn on unattended operations and set how often each one runs.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && <p className="text-sm text-destructive">{error}</p>}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading automation settings…</p>
        ) : (
          AUTOMATION_OPERATIONS.map(({ operation, title, description, toggleLabel, icon: Icon }) => {
            const schedule = scheduleByOperation.get(operation) ?? null;
            const isOpen = openOperation === operation;
            const isBusy = busyOperation === operation;

            return (
              <Collapsible
                key={operation}
                open={isOpen}
                onOpenChange={(open) => setOpenOperation(open ? operation : null)}
                className="rounded-md border"
              >
                <CollapsibleTrigger className="rounded-md p-4 hover:bg-accent/50">
                  <span className="flex flex-1 items-start gap-3">
                    <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span>
                      <span className="block font-medium">{title}</span>
                      <span className="block text-sm text-muted-foreground">{description}</span>
                    </span>
                  </span>
                  <IconChevronDown
                    className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
                    aria-hidden="true"
                  />
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="space-y-4 border-t p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium">{toggleLabel}</span>
                      <Switch
                        aria-label={toggleLabel}
                        checked={schedule?.enabled ?? false}
                        disabled={isBusy}
                        onCheckedChange={(checked) => void handleToggle(operation, title, checked)}
                      />
                    </div>

                    <div className="space-y-1">
                      <label htmlFor={`cron-${operation}`} className="text-sm font-medium">
                        Cron expression
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Set the schedule using the cron format. For more information please refer
                        to e.g.{" "}
                        <a
                          href="https://crontab.guru"
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-0.5 underline"
                        >
                          Crontab Guru
                          <IconExternalLink className="h-3 w-3" aria-hidden="true" />
                        </a>
                      </p>
                      <input
                        id={`cron-${operation}`}
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                        value={expressionFor(operation)}
                        disabled={isBusy}
                        onChange={(event) =>
                          setExpressionDrafts((current) => ({ ...current, [operation]: event.target.value }))
                        }
                        onBlur={() => void handleExpressionCommit(operation, title)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.currentTarget.blur();
                          }
                        }}
                      />
                      {expressionErrors[operation] && (
                        <p className="text-sm text-destructive">{expressionErrors[operation]}</p>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs text-muted-foreground">
                        Next: {formatTimestamp(schedule?.next_run_at)} | Last:{" "}
                        {formatTimestamp(schedule?.last_run_at)} | Result: {schedule?.last_run_result ?? "-"}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!schedule}
                        onClick={() => schedule && void handleRunNow(schedule)}
                      >
                        <IconPlayerPlay className="h-4 w-4" aria-hidden="true" />
                        Run Now
                      </Button>
                    </div>
                    {runMessages[operation] && (
                      <p className="text-sm text-status-good">{runMessages[operation]}</p>
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
