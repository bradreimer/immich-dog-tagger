import { useCallback, useEffect, useState } from "react";

import { getDogs, getLearningMetrics } from "../../lib/api";
import type { LearningMetrics } from "../../types/metrics";
import {
  IconBolt,
  IconBooks,
  IconCircleCheck,
  IconClipboardList,
  IconHistory,
  IconQuestionMark,
  IconRefresh,
  IconTargetArrow,
  IconTrendingDown,
  IconTrendingUp,
  IconUserCheck,
  IconX,
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
import { ProgressOverTimeChart, type ProgressPassPoint } from "./components/ProgressOverTimeChart";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function formatPercent(value: number | null): string {
  return value !== null ? `${Math.round(value * 100)}%` : "—";
}

function shareOfEligible(value: number, eligibleCount: number): string | undefined {
  return eligibleCount > 0 ? `${Math.round((value / eligibleCount) * 100)}% of eligible` : undefined;
}

function ProgressFooterStats({
  pass,
  activeDogCount,
  reduction,
  reductionSincePassId,
}: {
  pass: ProgressPassPoint;
  activeDogCount: number | null;
  /** undefined = don't show the tile (not enough history yet); null = show it with a dash. */
  reduction: number | null | undefined;
  reductionSincePassId: number | null;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <StatTile
        icon={IconBooks}
        tone="accent"
        label="Labeled Examples"
        value={pass.labeledExampleCount}
        subtext={activeDogCount !== null ? `Across ${activeDogCount} dog${activeDogCount === 1 ? "" : "s"}` : undefined}
      />
      <StatTile
        icon={IconCircleCheck}
        tone="good"
        label="Confidently Classified"
        value={pass.confidentCount}
        subtext={shareOfEligible(pass.confidentCount, pass.eligibleCount)}
      />
      <StatTile
        icon={IconQuestionMark}
        tone="warning"
        label="Needs Review"
        value={pass.needsReviewCount}
        subtext={shareOfEligible(pass.needsReviewCount, pass.eligibleCount)}
      />
      <StatTile
        icon={IconX}
        tone="serious"
        label="Unknown"
        value={pass.unknownCount}
        subtext={shareOfEligible(pass.unknownCount, pass.eligibleCount)}
      />
      {reduction !== undefined && (
        <StatTile
          icon={reduction !== null && reduction < 0 ? IconTrendingUp : IconTrendingDown}
          tone={reduction === null ? "neutral" : reduction >= 0 ? "good" : "serious"}
          label="Review Queue Reduction"
          value={reduction !== null ? `${Math.abs(Math.round(reduction * 100))}%` : "—"}
          subtext={
            reduction !== null && reductionSincePassId !== null
              ? `since pass #${reductionSincePassId}`
              : "starting queue was empty"
          }
        />
      )}
    </div>
  );
}

export function MetricsPage() {
  const [metrics, setMetrics] = useState<LearningMetrics | null>(null);
  const [activeDogCount, setActiveDogCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [learningMetrics, dogs] = await Promise.all([
        getLearningMetrics(),
        getDogs({ includeInactive: false }).catch(() => null),
      ]);
      setMetrics(learningMetrics);
      setActiveDogCount(dogs ? dogs.length : null);
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
  // rather than rendering a fabricated 0 for "not recorded". "Needs Review" plots
  // review_queue_size (not the legacy, effectively-always-zero needs_review_count field) --
  // see DT-1108 for why.
  const chartPasses: ProgressPassPoint[] = passHistory
    .filter((pass) => pass.review_queue_size !== null && pass.labeled_example_count !== null)
    .map((pass) => ({
      id: pass.id,
      eligibleCount: pass.eligible_count,
      confidentCount: pass.confident_count,
      needsReviewCount: pass.review_queue_size as number,
      unknownCount: pass.unknown_count,
      labeledExampleCount: pass.labeled_example_count as number,
    }));

  // Reduction in the needs-review queue between the first and most recently recorded
  // qualifying pass -- not "since initial", since no pass snapshot exists before the first
  // Reclassify run (ClassificationPass rows are only ever created by ReclassifyService).
  const reductionSinceFirst =
    chartPasses.length < 2
      ? undefined
      : chartPasses[0].needsReviewCount === 0
        ? null
        : 1 - chartPasses[chartPasses.length - 1].needsReviewCount / chartPasses[0].needsReviewCount;

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

      {metrics && (
        <Card>
          <CardHeader>
            <CardTitle>Progress Over Time</CardTitle>
            <CardDescription>By reclassification pass.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {chartPasses.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Run the pipeline and review your first batch of images. Your progress will appear
                here after your first Reclassify pass.
              </p>
            ) : chartPasses.length === 1 ? (
              <>
                <p className="text-sm text-muted-foreground">
                  One pass recorded so far -- trends will appear after your next Reclassify pass.
                </p>
                <ProgressFooterStats
                  pass={chartPasses[0]}
                  activeDogCount={activeDogCount}
                  reduction={undefined}
                  reductionSincePassId={null}
                />
              </>
            ) : (
              <>
                <ProgressOverTimeChart passes={chartPasses} />
                <ProgressFooterStats
                  pass={chartPasses[chartPasses.length - 1]}
                  activeDogCount={activeDogCount}
                  reduction={reductionSinceFirst}
                  reductionSincePassId={chartPasses[0].id}
                />
              </>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  );
}
