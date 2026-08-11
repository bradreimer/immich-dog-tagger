import { useCallback, useEffect, useState } from "react";

import { getLearningMetrics } from "../../lib/api";
import type { ClassificationPassSummary, LearningMetrics } from "../../types/metrics";
import { IconRefresh } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function CoverageSparkline({ passes }: { passes: ClassificationPassSummary[] }) {
  const width = 160;
  const height = 32;

  const points = passes.map((pass) =>
    pass.eligible_count > 0 ? pass.confident_count / pass.eligible_count : 0,
  );

  const max = Math.max(...points, 0.01);
  const min = Math.min(...points, 0);
  const range = Math.max(max - min, 0.01);

  const coords = points.map((value, index) => ({
    x: (index / (points.length - 1)) * width,
    y: height - ((value - min) / range) * height,
    value,
  }));

  const path = coords
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Confident coverage trend over the last ${points.length} reclassification passes`}
      className="shrink-0 overflow-visible text-amber-500"
    >
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {coords.map((point, index) => (
        <circle key={passes[index].id} cx={point.x} cy={point.y} r={2.5} fill="currentColor">
          <title>{`Pass #${passes[index].id}: ${Math.round(point.value * 100)}% confident`}</title>
        </circle>
      ))}
    </svg>
  );
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
          <CardHeader>
            <CardTitle>Learning Progress</CardTitle>
            <CardDescription>
              Every count states its denominator explicitly. This is a similarity score against
              your own reviewed examples, not a calibrated accuracy or probability.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Confident coverage</p>
                <p className="mt-1 text-2xl font-semibold">
                  {metrics.coverage !== null ? `${Math.round(metrics.coverage * 100)}%` : "—"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {metrics.confident_count} of {metrics.eligible_count} eligible crops
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Review rate</p>
                <p className="mt-1 text-2xl font-semibold">
                  {metrics.review_rate !== null ? `${Math.round(metrics.review_rate * 100)}%` : "—"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {metrics.reviewed_count} of {metrics.eligible_count} reviewed
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Labeled examples</p>
                <p className="mt-1 text-2xl font-semibold">{metrics.labeled_example_count}</p>
                <p className="text-xs text-muted-foreground">
                  {metrics.needs_review_count} needs review · {metrics.unknown_count} unknown
                </p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Last Reclassify</p>
                {metrics.last_reclassification ? (
                  <>
                    <p
                      className={`mt-1 font-medium ${
                        metrics.last_reclassification.status === "completed"
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-rose-600 dark:text-rose-400"
                      }`}
                    >
                      {metrics.last_reclassification.status === "completed" ? "Completed" : "Failed"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatTimestamp(metrics.last_reclassification.completed_at)} ·{" "}
                      {metrics.last_reclassification.changed_count} changed
                    </p>
                  </>
                ) : (
                  <p className="mt-1 font-medium text-muted-foreground">Never run</p>
                )}
              </div>
            </div>

            {metrics.pass_history.length >= 2 && (
              <div className="flex items-center gap-3 rounded-md border p-3">
                <CoverageSparkline passes={metrics.pass_history} />
                <p className="text-xs text-muted-foreground">
                  Confident coverage across the last {metrics.pass_history.length} reclassification
                  passes.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  );
}
