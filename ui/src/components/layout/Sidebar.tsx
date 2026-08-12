import { useEffect, useState } from "react";
import {
  IconChartBar,
  IconChecklist,
  IconLayoutDashboard,
  IconListDetails,
} from "@tabler/icons-react";
import { getReviewStats } from "../../lib/api";
import { ThemeToggle } from "../theme/ThemeToggle";

interface Props {
  currentPath: string;
  onNavigate: (path: string) => void;
}

const links = [
  { label: "Mission Control", path: "/", icon: IconLayoutDashboard },
  { label: "Review", path: "/review", icon: IconChecklist },
  { label: "Job Queue", path: "/jobs", icon: IconListDetails },
  { label: "Metrics", path: "/metrics", icon: IconChartBar },
];

export function Sidebar({ currentPath, onNavigate }: Props) {
  const [reviewRemaining, setReviewRemaining] = useState<number | null>(null);

  useEffect(() => {
    getReviewStats()
      .then((stats) => setReviewRemaining(stats.remaining))
      .catch(() => setReviewRemaining(null));
  }, [currentPath]);

  return (
    <aside className="flex h-screen w-16 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:w-64">
      <div className="flex items-center gap-3 px-3 py-4 md:px-5">
        <img
          src="/logo_on_black.png"
          alt="Immich Dog Tagger"
          className="h-9 w-9 flex-shrink-0 rounded-lg object-contain"
        />
        <div className="hidden min-w-0 md:block">
          <p className="truncate text-sm font-semibold tracking-tight">Dog Tagger</p>
          <p className="truncate text-xs text-sidebar-foreground/60">Local dog recognition</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2 py-2 md:px-3" aria-label="Main navigation">
        {links.map((link) => {
          const isActive = currentPath === link.path;
          const Icon = link.icon;
          return (
            <button
              key={link.path}
              type="button"
              aria-current={isActive ? "page" : undefined}
              className={
                isActive
                  ? "flex items-center gap-3 rounded-lg bg-sidebar-primary px-3 py-2.5 text-sm font-medium text-sidebar-primary-foreground"
                  : "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
              }
              onClick={() => onNavigate(link.path)}
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
              <span className="hidden truncate md:inline">{link.label}</span>
              {link.path === "/review" && reviewRemaining !== null && reviewRemaining > 0 && (
                <span
                  className="ml-auto hidden shrink-0 rounded-full bg-status-warning px-2 py-0.5 text-xs font-semibold text-black/80 md:inline-block"
                  aria-label={`${reviewRemaining} items awaiting review`}
                >
                  {reviewRemaining}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="flex items-center justify-center border-t border-sidebar-border px-3 py-3 md:justify-start md:px-5">
        <ThemeToggle />
      </div>
    </aside>
  );
}
