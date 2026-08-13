import { useEffect, useState } from "react";
import {
  IconChartBar,
  IconChecklist,
  IconDog,
  IconLayoutDashboard,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconListDetails,
  IconPhoto,
} from "@tabler/icons-react";
import { getReviewStats } from "../../lib/api";
import { cn } from "../../lib/utils";
import { ThemeToggle } from "../theme/ThemeToggle";

interface Props {
  currentPath: string;
  onNavigate: (path: string) => void;
}

const links = [
  { label: "Overview", path: "/", icon: IconLayoutDashboard },
  { label: "Review", path: "/review", icon: IconChecklist },
  { label: "Library", path: "/library", icon: IconPhoto },
  { label: "Dogs & Cats", path: "/dogs", icon: IconDog },
  { label: "Job Queue", path: "/jobs", icon: IconListDetails },
  { label: "Metrics", path: "/metrics", icon: IconChartBar },
];

const COLLAPSE_STORAGE_KEY = "dogtagger.sidebar-collapsed";

function readStoredCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function Sidebar({ currentPath, onNavigate }: Props) {
  const [reviewRemaining, setReviewRemaining] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState(readStoredCollapsed);

  useEffect(() => {
    getReviewStats()
      .then((stats) => setReviewRemaining(stats.remaining))
      .catch(() => setReviewRemaining(null));
  }, [currentPath]);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      // Ignore -- collapsed state just won't persist across reloads.
    }
  }, [collapsed]);

  return (
    <aside
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-150",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div className="flex shrink-0 items-center gap-3 px-3 py-4">
        <img
          src="/logo_on_black.png"
          alt="Immich Dog Tagger"
          className="h-9 w-9 flex-shrink-0 rounded-lg object-contain"
        />
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">Dog Tagger</p>
            <p className="truncate text-xs text-sidebar-foreground/60">Local dog recognition</p>
          </div>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-2" aria-label="Main navigation">
        {links.map((link) => {
          const isActive = currentPath === link.path;
          const Icon = link.icon;
          return (
            <button
              key={link.path}
              type="button"
              aria-current={isActive ? "page" : undefined}
              title={collapsed ? link.label : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm",
                collapsed && "justify-center",
                isActive
                  ? "bg-sidebar-primary font-medium text-sidebar-primary-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )}
              onClick={() => onNavigate(link.path)}
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
              {!collapsed && <span className="truncate">{link.label}</span>}
              {!collapsed && link.path === "/review" && reviewRemaining !== null && reviewRemaining > 0 && (
                <span
                  className="ml-auto shrink-0 rounded-full bg-status-warning px-2 py-0.5 text-xs font-semibold text-black/80"
                  aria-label={`${reviewRemaining} items awaiting review`}
                >
                  {reviewRemaining}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div
        className={cn(
          "flex shrink-0 gap-2 border-t border-sidebar-border p-3",
          collapsed ? "flex-col items-center" : "flex-row items-center justify-between",
        )}
      >
        <ThemeToggle />
        <button
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex size-10 shrink-0 items-center justify-center rounded-md text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
          onClick={() => setCollapsed((current) => !current)}
        >
          {collapsed ? (
            <IconLayoutSidebarLeftExpand className="h-5 w-5" aria-hidden="true" />
          ) : (
            <IconLayoutSidebarLeftCollapse className="h-5 w-5" aria-hidden="true" />
          )}
        </button>
      </div>
    </aside>
  );
}
