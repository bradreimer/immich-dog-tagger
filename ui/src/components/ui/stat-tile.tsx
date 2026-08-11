import type { ComponentType, SVGProps } from "react";
import { cn } from "@/lib/utils";

export type StatTileTone = "good" | "warning" | "serious" | "critical" | "info" | "accent" | "neutral";

const toneClasses: Record<StatTileTone, string> = {
  good: "bg-status-good/12 text-status-good",
  warning: "bg-status-warning/15 text-status-warning",
  serious: "bg-status-serious/15 text-status-serious",
  critical: "bg-status-critical/12 text-status-critical",
  info: "bg-status-info/12 text-status-info",
  accent: "bg-chart-3/15 text-chart-3",
  neutral: "bg-muted text-muted-foreground",
};

const progressClasses: Record<StatTileTone, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  serious: "bg-status-serious",
  critical: "bg-status-critical",
  info: "bg-status-info",
  accent: "bg-chart-3",
  neutral: "bg-muted-foreground",
};

interface Props {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  tone: StatTileTone;
  label: string;
  value: string | number;
  subtext?: string;
  /** 0-1 inclusive. When provided, renders a thin inline progress bar under the subtext. */
  progress?: number | null;
  className?: string;
}

export function StatTile({ icon: Icon, tone, label, value, subtext, progress, className }: Props) {
  return (
    <div className={cn("rounded-lg border p-4", className)}>
      <div className="flex items-start gap-3">
        <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-full", toneClasses[tone])}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
        </div>
      </div>

      {progress !== null && progress !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted" role="presentation">
          <div
            className={cn("h-full rounded-full", progressClasses[tone])}
            style={{ width: `${Math.max(0, Math.min(1, progress)) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
