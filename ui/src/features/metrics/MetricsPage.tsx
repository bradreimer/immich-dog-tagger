import { useCallback, useEffect, useState } from "react";

import { getLearningMetrics } from "../../lib/api";
import type { LearningMetrics } from "../../types/metrics";
import {
  IconBolt,
  IconBooks,
  IconClipboardList,
  IconHistory,
  IconRefresh,
  IconTargetArrow,
  IconUserCheck,
} from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import { DonutChart } from "./components/DonutChart";
import { TrendChart } from "./components/TrendChart";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function formatPercent(value: number | null): string {
  return value !== null ? `${Math.round(value * 100)}%` : "—";
}

export function MetricsPage() {
  const [metrics, setMetrics] = useState<LearningMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setMetrics(await getLearningMetrics());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const passHistory = metrics?.pass_history ?? [];
  // review_queue_size/labeled_example_count are nullable on passes recorded before DT-1101
  // shipped and are never backfilled -- only plot the contiguous data that actually exists
  // rather than rendering a fabricated 0 for "not recorded".
  const queueTrendPasses = passHistory.filter((pass) => pass.review_queue_size !== null);
  const labeledTrendPasses = passHistory.filter((pass) => pass.labeled_example_count !== null);
  const hasQueueTrend = queueTrendPasses.length >= 2;
  const hasLabeledTrend = labeledTrendPasses.length >= 2;

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Metrics</h1>
          <p className="text-muted-foreground">
            How much manual review is still needed, based on what's stored in the database.
          </p>
        </div>

        <Button variant="outline" onClick={() => load()} disabled={loading}>
          <IconRefresh className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </header>

      {error && (
        <Card>
          <CardHeader>
            <CardTitle>Metrics Error</CardTitle>
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

      {!metrics && !error && !loading && (
        <Card>
          <CardHeader>
            <CardTitle>No data yet</CardTitle>
            <CardDescription>Run the pipeline to start classifying crops.</CardDescription>
          </CardHeader>
        </Card>
      )}

      {metrics && (
        <Card>
          <CardContent className="grid gap-6 p-6 sm:grid-cols-[1.1fr_1fr] sm:items-center">
            <div className="space-y-1">
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-status-info">
                Automation
              </p>
              <p className="text-5xl font-bold tracking-tight">{formatPercent(metrics.automation_rate)}</p>
              <p className="text-sm text-muted-foreground">
                {metrics.no_review_needed_count} of {metrics.eligible_count} images require no
                manual review right now -- either confidently classified, or already reviewed.
              </p>
            </div>

            <DonutChart
              centerValue={formatPercent(metrics.automation_rate)}
              centerLabel="automated"
              segments={[
                { key: "confident", label: "Confident", value: metrics.confident_count, colorVar: "var(--status-good)" },
                { key: "queue", label: "Review queue", value: metrics.review_queue_size, colorVar: "var(--status-warning)" },
                { key: "unknown", label: "Unknown", value: metrics.unknown_count, colorVar: "var(--status-serious)" },
              ]}
            />
          </CardContent>
        </Card>
      )}

      {metrics && (
        <Card>
          <CardHeader>
            <CardTitle>Learning Progress</CardTitle>
            <CardDescription>
              Every count states its denominator explicitly. This is a similarity score against
              your own reviewed examples, not a calibrated accuracy or probability.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <StatTile
                icon={IconTargetArrow}
                tone="good"
                label="Confident coverage"
                value={formatPercent(metrics.coverage)}
                subtext={`${metrics.confident_count} of ${metrics.eligible_count} eligible crops`}
                progress={metrics.coverage}
              />
              <StatTile
                icon={IconUserCheck}
                tone="info"
                label="Review rate"
                value={formatPercent(metrics.review_rate)}
                subtext={`${metrics.reviewed_count} of ${metrics.eligible_count} reviewed`}
                progress={metrics.review_rate}
              />
              <StatTile
                icon={IconClipboardList}
                tone="warning"
                label="Review queue"
                value={metrics.review_queue_size}
                subtext={`awaiting review · ${metrics.unknown_count} unknown${
                  metrics.unknown_rate !== null ? ` (${formatPercent(metrics.unknown_rate)})` : ""
                }`}
              />
              <StatTile
                icon={IconBooks}
                tone="accent"
                label="Labeled examples"
                value={metrics.labeled_example_count}
                subtext="trusted reference examples for the classifier"
              />
              <StatTile
                icon={IconBolt}
                tone="info"
                label="Predictions changed"
                value={metrics.last_reclassification?.changed_count ?? 0}
                subtext={metrics.last_reclassification ? "in the last reclassification pass" : "no pass run yet"}
              />
              <StatTile
                icon={IconHistory}
                tone={
                  metrics.last_reclassification
                    ? metrics.last_reclassification.status === "completed"
                      ? "good"
                      : "critical"
                    : "neutral"
                }
                label="Last Reclassify"
                value={
                  metrics.last_reclassification
                    ? metrics.last_reclassification.status === "completed"
                      ? "Completed"
                      : "Failed"
                    : "Never run"
                }
                subtext={
                  metrics.last_reclassification
                    ? formatTimestamp(metrics.last_reclassification.completed_at)
                    : undefined
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {metrics && (hasQueueTrend || hasLabeledTrend) && (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          {hasQueueTrend && (
            <Card>
              <CardHeader>
                <CardTitle>Progress Over Time</CardTitle>
                <CardDescription>
                  Review queue, confident, and unknown counts across the last{" "}
                  {queueTrendPasses.length} reclassification passes.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TrendChart
                  unitLabel="eligible crops"
                  xLabels={queueTrendPasses.map((pass) => `#${pass.id}`)}
                  series={[
                    {
                      key: "queue",
                      label: "Review queue",
                      colorVar: "var(--status-warning)",
                      values: queueTrendPasses.map((p) => p.review_queue_size as number),
                    },
                    {
                      key: "confident",
                      label: "Confident",
                      colorVar: "var(--status-good)",
                      values: queueTrendPasses.map((p) => p.confident_count),
                    },
                    {
                      key: "unknown",
                      label: "Unknown",
                      colorVar: "var(--status-serious)",
                      values: queueTrendPasses.map((p) => p.unknown_count),
                    },
                  ]}
                />
              </CardContent>
            </Card>
          )}

          {hasLabeledTrend && (
            <Card>
              <CardHeader>
                <CardTitle>Labeled Examples</CardTitle>
                <CardDescription>Trusted reference examples, same passes.</CardDescription>
              </CardHeader>
              <CardContent>
                <TrendChart
                  unitLabel="labeled examples"
                  xLabels={labeledTrendPasses.map((pass) => `#${pass.id}`)}
                  series={[
                    {
                      key: "labeled",
                      label: "Labeled examples",
                      colorVar: "var(--chart-3)",
                      values: labeledTrendPasses.map((p) => p.labeled_example_count as number),
                    },
                  ]}
                />
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </section>
  );
}
