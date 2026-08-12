interface Segment {
  key: string;
  label: string;
  value: number;
  colorVar: string;
}

interface Props {
  segments: Segment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
}

const GAP_DEGREES = 3;

export function DonutChart({ segments, size = 168, thickness = 22, centerLabel, centerValue }: Props) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const gapLength = (GAP_DEGREES / 360) * circumference;

  let cumulative = 0;
  const arcs = segments.map((segment) => {
    const fraction = total > 0 ? segment.value / total : 0;
    const rawLength = fraction * circumference;
    const arcLength = Math.max(rawLength - gapLength, 0);
    const offset = -cumulative;
    cumulative += rawLength;

    return { ...segment, fraction, arcLength, offset };
  });

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${segments.map((s) => `${s.label}: ${s.value}`).join(", ")}, of ${total} total`}
        className="shrink-0"
      >
        <g transform={`translate(${size / 2}, ${size / 2}) rotate(-90)`}>
          <circle r={radius} fill="none" stroke="var(--border)" strokeWidth={thickness} />
          {arcs.map((arc) => (
            <circle
              key={arc.key}
              r={radius}
              fill="none"
              stroke={arc.colorVar}
              strokeWidth={thickness}
              strokeDasharray={`${arc.arcLength} ${circumference - arc.arcLength}`}
              strokeDashoffset={arc.offset}
              strokeLinecap="butt"
            >
              <title>
                {arc.label}: {arc.value} ({Math.round(arc.fraction * 100)}%)
              </title>
            </circle>
          ))}
        </g>
        {centerValue && (
          <text
            x={size / 2}
            y={centerLabel ? size / 2 - 4 : size / 2 + 6}
            textAnchor="middle"
            className="fill-foreground text-xl font-semibold"
          >
            {centerValue}
          </text>
        )}
        {centerLabel && (
          <text
            x={size / 2}
            y={size / 2 + 16}
            textAnchor="middle"
            className="fill-muted-foreground text-[10px] uppercase tracking-wide"
          >
            {centerLabel}
          </text>
        )}
      </svg>

      <ul className="w-full space-y-2 text-sm">
        {segments.map((segment) => {
          const fraction = total > 0 ? segment.value / total : 0;
          return (
            <li key={segment.key} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: segment.colorVar }}
                  aria-hidden="true"
                />
                {segment.label}
              </span>
              <span className="font-medium tabular-nums">
                {segment.value} ({Math.round(fraction * 100)}%)
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
