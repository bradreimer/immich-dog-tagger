import { useState } from "react";

import { downsampleForDisplay } from "../utils/downsample";

export interface ProgressPassPoint {
  id: number;
  eligibleCount: number;
  confidentCount: number;
  needsReviewCount: number;
  unknownCount: number;
  labeledExampleCount: number;
}

interface Props {
  passes: ProgressPassPoint[];
}

const WIDTH = 760;
const HEIGHT = 360;
const PAD_LEFT = 52;
const PAD_RIGHT = 64;
const PAD_TOP = 16;
const PAD_BOTTOM = 32;
const GRID_STEPS = 4;
// Above this many passes, only a sampled subset is plotted (see
// downsampleForDisplay) so the line stays legible instead of one
// increasingly cramped point per pass -- the first and last pass are
// always kept so the chart still spans the full recorded history.
const MAX_DISPLAY_POINTS = 20;

const COLOR_NEEDS_REVIEW = "var(--status-warning)";
const COLOR_CONFIDENT = "var(--status-good)";
const COLOR_UNKNOWN = "var(--status-serious)";
const COLOR_LABELED = "var(--chart-3)";

function niceMax(value: number): number {
  return Math.max(1, value);
}

export function ProgressOverTimeChart({ passes }: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  // Plot a sampled subset for legibility, but scale the axes and compute
  // the "since pass #N" comparisons off the full history -- a value that
  // got sampled out shouldn't shrink the axis or change what "first pass"
  // means.
  const displayPasses = downsampleForDisplay(passes, MAX_DISPLAY_POINTS);
  const pointCount = displayPasses.length;

  const leftMax = niceMax(Math.max(...passes.flatMap((p) => [p.needsReviewCount, p.confidentCount, p.unknownCount])));
  const rightMax = niceMax(Math.max(...passes.map((p) => p.labeledExampleCount)));

  const firstQualifying = passes[0];
  const reductionSince = (pass: ProgressPassPoint): number | null => {
    if (firstQualifying.needsReviewCount === 0) {
      return null;
    }
    return 1 - pass.needsReviewCount / firstQualifying.needsReviewCount;
  };

  // Inset the plotted points from the axes so edge labels don't collide with axis tick labels.
  const X_INSET = 24;
  const xAt = (index: number) =>
    pointCount > 1
      ? PAD_LEFT + X_INSET + (index / (pointCount - 1)) * (plotWidth - 2 * X_INSET)
      : PAD_LEFT + plotWidth / 2;
  const yLeftAt = (value: number) => PAD_TOP + plotHeight - (value / leftMax) * plotHeight;
  const yRightAt = (value: number) => PAD_TOP + plotHeight - (value / rightMax) * plotHeight;

  const pathFor = (values: number[], yAt: (v: number) => number) =>
    values.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`).join(" ");

  const gridRows = Array.from({ length: GRID_STEPS + 1 }, (_, i) => ({
    y: PAD_TOP + plotHeight - (plotHeight * i) / GRID_STEPS,
    leftValue: Math.round((leftMax * i) / GRID_STEPS),
    rightValue: Math.round((rightMax * i) / GRID_STEPS),
  }));

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX = ((event.clientX - rect.left) / rect.width) * WIDTH;
    if (pointCount <= 1) {
      setHoverIndex(0);
      return;
    }
    const raw = ((relativeX - PAD_LEFT) / plotWidth) * (pointCount - 1);
    setHoverIndex(Math.min(pointCount - 1, Math.max(0, Math.round(raw))));
  };

  const series: Array<{
    key: string;
    label: string;
    color: string;
    dashed?: boolean;
    values: number[];
    yAt: (v: number) => number;
    labelOffset: number;
  }> = [
    {
      key: "needsReview",
      label: "Needs Review",
      color: COLOR_NEEDS_REVIEW,
      values: displayPasses.map((p) => p.needsReviewCount),
      yAt: yLeftAt,
      labelOffset: -10,
    },
    {
      key: "confident",
      label: "Confidently Classified",
      color: COLOR_CONFIDENT,
      values: displayPasses.map((p) => p.confidentCount),
      yAt: yLeftAt,
      labelOffset: -10,
    },
    {
      key: "unknown",
      label: "Unknown",
      color: COLOR_UNKNOWN,
      values: displayPasses.map((p) => p.unknownCount),
      yAt: yLeftAt,
      labelOffset: 16,
    },
    {
      key: "labeled",
      label: "Labeled Examples",
      color: COLOR_LABELED,
      dashed: true,
      values: displayPasses.map((p) => p.labeledExampleCount),
      yAt: yRightAt,
      labelOffset: 16,
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span
                className="h-0.5 w-4 shrink-0"
                style={{ backgroundColor: s.color, opacity: s.dashed ? 0.7 : 1 }}
                aria-hidden="true"
              />
              {s.label}
            </li>
          ))}
        </ul>
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          Hover a pass for details
        </p>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          width="100%"
          height={HEIGHT}
          role="img"
          aria-label={`Needs review, confidently classified, unknown, and labeled example counts across ${passes.length} reclassification passes${pointCount < passes.length ? `, sampled to ${pointCount} points` : ""}`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
          className="overflow-visible"
        >
          {gridRows.map((row) => (
            <g key={row.y}>
              <line x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={row.y} y2={row.y} stroke="var(--border)" strokeWidth={1} />
              <text x={PAD_LEFT - 8} y={row.y + 3} textAnchor="end" className="fill-muted-foreground text-[10px]">
                {row.leftValue}
              </text>
              <text
                x={WIDTH - PAD_RIGHT + 8}
                y={row.y + 3}
                textAnchor="start"
                className="text-[10px]"
                style={{ fill: COLOR_LABELED }}
              >
                {row.rightValue}
              </text>
            </g>
          ))}

          <text
            x={14}
            y={PAD_TOP + plotHeight / 2}
            textAnchor="middle"
            className="fill-muted-foreground text-[10px]"
            transform={`rotate(-90 14 ${PAD_TOP + plotHeight / 2})`}
          >
            Images / Crops
          </text>
          <text
            x={WIDTH - 14}
            y={PAD_TOP + plotHeight / 2}
            textAnchor="middle"
            className="text-[10px]"
            style={{ fill: COLOR_LABELED }}
            transform={`rotate(90 ${WIDTH - 14} ${PAD_TOP + plotHeight / 2})`}
          >
            Labeled Examples
          </text>

          {displayPasses.map((pass, i) => (
            <text key={pass.id} x={xAt(i)} y={HEIGHT - 8} textAnchor="middle" className="fill-muted-foreground text-[10px]">
              Pass #{pass.id}
            </text>
          ))}

          {hoverIndex !== null && (
            <line
              x1={xAt(hoverIndex)}
              x2={xAt(hoverIndex)}
              y1={PAD_TOP}
              y2={PAD_TOP + plotHeight}
              stroke="var(--muted-foreground)"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
          )}

          {series.map((s) => (
            <g key={s.key}>
              <path
                d={pathFor(s.values, s.yAt)}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={s.dashed ? "6 4" : undefined}
                opacity={s.dashed ? 0.85 : 1}
              />
              {s.values.map((v, i) => (
                <g key={i}>
                  <circle
                    cx={xAt(i)}
                    cy={s.yAt(v)}
                    r={hoverIndex === i ? 4.5 : 3}
                    fill={s.color}
                    stroke="var(--card)"
                    strokeWidth={1.5}
                  />
                  <text
                    x={xAt(i)}
                    y={s.yAt(v) + s.labelOffset}
                    textAnchor="middle"
                    className="text-[10px] font-medium"
                    style={{ fill: s.color }}
                  >
                    {v}
                  </text>
                </g>
              ))}
            </g>
          ))}
        </svg>

        {hoverIndex !== null && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
            style={{ left: `${(xAt(hoverIndex) / WIDTH) * 100}%` }}
          >
            <p className="mb-1.5 font-medium">Pass #{displayPasses[hoverIndex].id}</p>
            <div className="space-y-0.5">
              <p className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: COLOR_LABELED }} aria-hidden="true" />
                Labeled examples: <span className="font-medium text-foreground">{displayPasses[hoverIndex].labeledExampleCount}</span>
              </p>
              <p className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: COLOR_CONFIDENT }} aria-hidden="true" />
                Confidently classified: <span className="font-medium text-foreground">{displayPasses[hoverIndex].confidentCount}</span>
              </p>
              <p className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: COLOR_NEEDS_REVIEW }} aria-hidden="true" />
                Needs review: <span className="font-medium text-foreground">{displayPasses[hoverIndex].needsReviewCount}</span>
              </p>
              <p className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: COLOR_UNKNOWN }} aria-hidden="true" />
                Unknown: <span className="font-medium text-foreground">{displayPasses[hoverIndex].unknownCount}</span>
              </p>
            </div>
            <div className="mt-1.5 border-t pt-1.5 text-muted-foreground">
              <p>{displayPasses[hoverIndex].eligibleCount} eligible items</p>
              {(() => {
                const reduction = reductionSince(displayPasses[hoverIndex]);
                if (reduction === null || hoverIndex === 0) {
                  return null;
                }
                return (
                  <p className={reduction >= 0 ? "font-medium text-status-good" : "font-medium text-status-serious"}>
                    Needs-review queue {reduction >= 0 ? "↓" : "↑"} {Math.abs(Math.round(reduction * 100))}% since pass #
                    {firstQualifying.id}
                  </p>
                );
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
