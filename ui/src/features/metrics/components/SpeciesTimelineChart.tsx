import { useEffect, useRef, useState } from "react";

import type { SpeciesTimelinePoint } from "../../../types/metrics";

interface Props {
  title: string;
  identities: string[];
  points: SpeciesTimelinePoint[];
}

const DEFAULT_WIDTH = 760;
const HEIGHT = 320;
const PAD_LEFT = 52;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 28;
const GRID_STEPS = 4;

// Positional, not per-identity-name: identities[0..5] (the top-N pets) get
// their own band, and "Other" -- always last in `identities` when present --
// lands on the 7th. Order is blue/aqua/violet/yellow/magenta/green/red, the
// dataviz skill's validated categorical order for this exact 7-hue set
// (node scripts/validate_palette.js; see index.css's --chart-6/7 comment) --
// not this app's original 5-color DT-1104 set (blue/aqua/violet/yellow/red)
// in slot-number order, since inserting magenta/green there would put
// yellow and a warm color adjacent in a way that failed validation.
const BAND_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-5)",
];

function colorFor(index: number): string {
  return BAND_COLORS[index] ?? BAND_COLORS[BAND_COLORS.length - 1];
}

function niceMax(value: number): number {
  return Math.max(1, value);
}

type Point = [number, number];

// Catmull-Rom-to-cubic-Bezier conversion (uniform, tension 1/6): produces a
// smooth curve that still passes exactly through every input point, so the
// true stacked total at each plotted point is preserved -- only the curve
// drawn *between* points changes.
function smoothPathSegment(pts: Point[], startCommand: "M" | "L"): string {
  if (pts.length === 0) {
    return "";
  }
  if (pts.length === 1) {
    return `${startCommand} ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  }

  let d = `${startCommand} ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)} ${cp2x.toFixed(1)} ${cp2y.toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}

export function SpeciesTimelineChart({ title, identities, points }: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [isolated, setIsolated] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);

  // Fill the card's actual available width instead of a fixed pixel width.
  useEffect(() => {
    const node = containerRef.current;
    if (!node) {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry && entry.contentRect.width > 0) {
        setWidth(entry.contentRect.width);
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const plotWidth = width - PAD_LEFT - PAD_RIGHT;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  // No downsampling: every year the API returns is plotted. Legibility at
  // high point counts comes from the full-width chart below, not from
  // dropping data.
  // A single year has no width to form a filled area -- duplicate it
  // across the full plot so it still reads as a stacked column instead of
  // a zero-width sliver.
  const plottedPoints = points.length === 1 ? [points[0], points[0]] : points;
  const pointCount = plottedPoints.length;

  // Only one identity can be isolated at a time; isolating rescales the Y
  // axis and tooltip to that identity alone rather than the full stack.
  const visibleIdentities = isolated ? identities.filter((name) => name === isolated) : identities;

  const totals = plottedPoints.map((point) =>
    visibleIdentities.reduce((sum, name) => sum + (point.counts[name] ?? 0), 0),
  );
  const maxTotal = niceMax(Math.max(...totals));

  const xAt = (index: number) =>
    pointCount > 1 ? PAD_LEFT + (index / (pointCount - 1)) * plotWidth : PAD_LEFT + plotWidth / 2;
  const yAt = (value: number) => PAD_TOP + plotHeight - (value / maxTotal) * plotHeight;

  // Stack bottom-up in `visibleIdentities` order: each band's bottom edge is
  // the previous band's top edge, so the bands never overlap. When isolated,
  // this reduces to a single band starting at zero.
  let cumulative = new Array(pointCount).fill(0) as number[];
  const bands = visibleIdentities.map((name) => {
    const bottoms = cumulative;
    const tops = plottedPoints.map((point, i) => cumulative[i] + (point.counts[name] ?? 0));
    cumulative = tops;
    return { name, color: colorFor(identities.indexOf(name)), bottoms, tops };
  });

  const areaPath = (bottoms: number[], tops: number[]) => {
    const topPts: Point[] = tops.map((v, i): Point => [xAt(i), yAt(v)]);
    const bottomPts: Point[] = bottoms.map((v, i): Point => [xAt(i), yAt(v)]).reverse();
    const top = smoothPathSegment(topPts, "M");
    const bottom = smoothPathSegment(bottomPts, "L");
    return `${top} ${bottom} Z`;
  };

  const gridRows = Array.from({ length: GRID_STEPS + 1 }, (_, i) => ({
    y: PAD_TOP + plotHeight - (plotHeight * i) / GRID_STEPS,
    value: Math.round((maxTotal * i) / GRID_STEPS),
  }));

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX = ((event.clientX - rect.left) / rect.width) * width;
    if (pointCount <= 1) {
      setHoverIndex(0);
      return;
    }
    const raw = ((relativeX - PAD_LEFT) / plotWidth) * (pointCount - 1);
    setHoverIndex(Math.min(pointCount - 1, Math.max(0, Math.round(raw))));
  };

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-x-2 gap-y-1 text-xs text-muted-foreground">
        {identities.map((name, index) => {
          const active = isolated === name;
          const dimmed = isolated !== null && !active;
          return (
            <li key={name}>
              <button
                type="button"
                onClick={() => setIsolated((current) => (current === name ? null : name))}
                aria-pressed={active}
                title={active ? `Showing only ${name}. Click to show all.` : `Show only ${name}`}
                className={`flex items-center gap-1.5 rounded px-1 py-0.5 transition-colors hover:bg-muted ${
                  dimmed ? "opacity-40" : ""
                }`}
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{ backgroundColor: colorFor(index) }}
                  aria-hidden="true"
                />
                {name}
              </button>
            </li>
          );
        })}
      </ul>

      <div ref={containerRef} className="relative">
        <svg
          viewBox={`0 0 ${width} ${HEIGHT}`}
          width="100%"
          height={HEIGHT}
          role="img"
          aria-label={`${title}: confirmed photo count per year, stacked by pet, across ${points.length} year(s)${isolated ? `, isolated to ${isolated}` : ""}`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
          className="overflow-visible"
        >
          {gridRows.map((row) => (
            <g key={row.y}>
              <line
                x1={PAD_LEFT}
                x2={width - PAD_RIGHT}
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
            style={{ left: `${(xAt(hoverIndex) / width) * 100}%` }}
          >
            <p className="mb-1.5 font-medium">{plottedPoints[hoverIndex].label}</p>
            <div className="space-y-0.5">
              {visibleIdentities.map((name) => (
                <p key={name} className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: colorFor(identities.indexOf(name)) }}
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
