import { useState } from "react";

export interface TrendSeries {
  key: string;
  label: string;
  colorVar: string;
  values: number[];
}

interface Props {
  series: TrendSeries[];
  xLabels: string[];
  height?: number;
  unitLabel: string;
}

const WIDTH = 560;
const PAD_LEFT = 40;
const PAD_RIGHT = 12;
const PAD_TOP = 12;
const PAD_BOTTOM = 28;

export function TrendChart({ series, xLabels, height = 220, unitLabel }: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const pointCount = xLabels.length;
  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotHeight = height - PAD_TOP - PAD_BOTTOM;

  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const gridSteps = 4;
  const gridValues = Array.from({ length: gridSteps + 1 }, (_, i) => Math.round((max / gridSteps) * i));

  const xAt = (index: number) =>
    pointCount > 1 ? PAD_LEFT + (index / (pointCount - 1)) * plotWidth : PAD_LEFT + plotWidth / 2;
  const yAt = (value: number) => PAD_TOP + plotHeight - (value / max) * plotHeight;

  const pathFor = (values: number[]) =>
    values.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`).join(" ");

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
    <div className="space-y-2">
      {series.length > 1 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: s.colorVar }}
                aria-hidden="true"
              />
              {s.label}
            </li>
          ))}
        </ul>
      )}

      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${height}`}
          width="100%"
          height={height}
          role="img"
          aria-label={`${series.map((s) => s.label).join(", ")} across ${pointCount} reclassification passes, in ${unitLabel}`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
          className="overflow-visible"
        >
          {gridValues.map((value) => (
            <g key={value}>
              <line
                x1={PAD_LEFT}
                x2={WIDTH - PAD_RIGHT}
                y1={yAt(value)}
                y2={yAt(value)}
                stroke="var(--border)"
                strokeWidth={1}
              />
              <text x={PAD_LEFT - 6} y={yAt(value) + 3} textAnchor="end" className="fill-muted-foreground text-[9px]">
                {value}
              </text>
            </g>
          ))}

          {xLabels.map((label, i) => (
            <text
              key={label}
              x={xAt(i)}
              y={height - 8}
              textAnchor="middle"
              className="fill-muted-foreground text-[9px]"
            >
              {label}
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
              <path d={pathFor(s.values)} fill="none" stroke={s.colorVar} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              {s.values.map((v, i) => (
                <circle
                  key={i}
                  cx={xAt(i)}
                  cy={yAt(v)}
                  r={hoverIndex === i ? 4.5 : 3}
                  fill={s.colorVar}
                  stroke="var(--card)"
                  strokeWidth={1.5}
                />
              ))}
            </g>
          ))}
        </svg>

        {hoverIndex !== null && (
          <div
            className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-md border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md"
            style={{ left: `${(xAt(hoverIndex) / WIDTH) * 100}%` }}
          >
            <p className="mb-1 font-medium">{xLabels[hoverIndex]}</p>
            {series.map((s) => (
              <p key={s.key} className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: s.colorVar }} aria-hidden="true" />
                {s.label}: <span className="font-medium text-foreground">{s.values[hoverIndex]}</span>
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
