import { useState } from "react";

import type { SpeciesTimelinePoint } from "../../../types/metrics";
import { downsampleForDisplay } from "../utils/downsample";

interface Props {
  title: string;
  identities: string[];
  points: SpeciesTimelinePoint[];
}

const WIDTH = 760;
const HEIGHT = 320;
const PAD_LEFT = 52;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 40;
const GRID_STEPS = 4;
// Same cap/rationale as ProgressOverTimeChart's MAX_DISPLAY_POINTS: keeps
// the chart legible across a long season history without losing the first
// or last recorded season.
const MAX_DISPLAY_POINTS = 20;

// Positional, not per-identity-name: identities[0..3] (the top-N pets) get
// chart-1..4, and "Other" -- always last in `identities` when present --
// lands on chart-5. Reuses this app's validated categorical palette
// (DT-1104) rather than inventing new colors.
const BAND_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

function colorFor(index: number): string {
  return BAND_COLORS[index] ?? BAND_COLORS[BAND_COLORS.length - 1];
}

function niceMax(value: number): number {
  return Math.max(1, value);
}

export function SpeciesTimelineChart({ title, identities, points }: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const displayPoints = downsampleForDisplay(points, MAX_DISPLAY_POINTS);
  // A single season has no width to form a filled area -- duplicate it
  // across the full plot so it still reads as a stacked column instead of
  // a zero-width sliver.
  const plottedPoints = displayPoints.length === 1 ? [displayPoints[0], displayPoints[0]] : displayPoints;
  const pointCount = plottedPoints.length;

  const totals = plottedPoints.map((point) =>
    identities.reduce((sum, name) => sum + (point.counts[name] ?? 0), 0),
  );
  const maxTotal = niceMax(Math.max(...totals));

  const xAt = (index: number) =>
    pointCount > 1 ? PAD_LEFT + (index / (pointCount - 1)) * plotWidth : PAD_LEFT + plotWidth / 2;
  const yAt = (value: number) => PAD_TOP + plotHeight - (value / maxTotal) * plotHeight;

  // Stack bottom-up in `identities` order: each band's bottom edge is the
  // previous band's top edge, so the bands never overlap.
  let cumulative = new Array(pointCount).fill(0) as number[];
  const bands = identities.map((name, index) => {
    const bottoms = cumulative;
    const tops = plottedPoints.map((point, i) => cumulative[i] + (point.counts[name] ?? 0));
    cumulative = tops;
    return { name, color: colorFor(index), bottoms, tops };
  });

  const areaPath = (bottoms: number[], tops: number[]) => {
    const top = tops
      .map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`)
      .join(" ");
    const bottom = bottoms
      .map((v, i) => `L ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`)
      .reverse()
      .join(" ");
    return `${top} ${bottom} Z`;
  };

  const gridRows = Array.from({ length: GRID_STEPS + 1 }, (_, i) => ({
    y: PAD_TOP + plotHeight - (plotHeight * i) / GRID_STEPS,
    value: Math.round((maxTotal * i) / GRID_STEPS),
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

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {identities.map((name, index) => (
          <li key={name} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: colorFor(index) }}
              aria-hidden="true"
            />
            {name}
          </li>
        ))}
      </ul>

      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          width="100%"
          height={HEIGHT}
          role="img"
          aria-label={`${title}: confirmed photo count per season, stacked by pet, across ${points.length} season(s)${pointCount < points.length ? `, sampled to ${pointCount} points` : ""}`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
          className="overflow-visible"
        >
          {gridRows.map((row) => (
            <g key={row.y}>
              <line
                x1={PAD_LEFT}
                x2={WIDTH - PAD_RIGHT}
                y1={row.y}
                y2={row.y}
                stroke="var(--border)"
                strokeWidth={1}
              />
              <text x={PAD_LEFT - 8} y={row.y + 3} textAnchor="end" className="fill-muted-foreground text-[10px]">
                {row.value}
              </text>
            </g>
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

          {bands.map((band) => (
            <path
              key={band.name}
              d={areaPath(band.bottoms, band.tops)}
              fill={band.color}
              opacity={0.85}
              stroke={band.color}
              strokeWidth={1}
            />
          ))}

          {plottedPoints.map((point, i) => (
            <text
              key={`${point.label}-${i}`}
              x={xAt(i)}
              y={HEIGHT - PAD_BOTTOM + 16}
              textAnchor="middle"
              className="fill-muted-foreground text-[10px]"
            >
              {point.label}
            </text>
          ))}
        </svg>

        {hoverIndex !== null && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
            style={{ left: `${(xAt(hoverIndex) / WIDTH) * 100}%` }}
          >
            <p className="mb-1.5 font-medium">{plottedPoints[hoverIndex].label}</p>
            <div className="space-y-0.5">
              {identities.map((name, index) => (
                <p key={name} className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: colorFor(index) }}
                    aria-hidden="true"
                  />
                  {name}:{" "}
                  <span className="font-medium text-foreground">
                    {plottedPoints[hoverIndex].counts[name] ?? 0}
                  </span>
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
