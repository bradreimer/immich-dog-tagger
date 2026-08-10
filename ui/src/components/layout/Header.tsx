import { ThemeToggle } from "../theme/ThemeToggle";

interface Props {
  currentPath: string;
  onNavigate: (path: string) => void;
}

export function Header({ currentPath, onNavigate }: Props) {
  const links = [
    { label: "Mission Control", shortLabel: "Control", path: "/" },
    { label: "Job Queue", shortLabel: "Jobs", path: "/jobs" },
    { label: "Review", shortLabel: "Review", path: "/review" },
  ];

  return (
    <header className="border-b bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.2),_transparent_45%),linear-gradient(135deg,_rgba(255,255,255,0.95),_rgba(254,242,242,0.9))] backdrop-blur supports-[backdrop-filter]:bg-white/70 dark:bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.18),_transparent_45%),linear-gradient(135deg,_rgba(17,24,39,0.95),_rgba(31,41,55,0.9))]">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:gap-4 sm:px-6 sm:py-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <img
            src="/banner.png"
            alt="Immich Dog Tagger"
            className="h-9 w-auto flex-shrink-0 rounded-lg object-cover shadow-sm ring-1 ring-black/10 dark:ring-white/10 sm:h-12"
          />
          <div className="min-w-0 space-y-0.5">
            <h1 className="truncate text-base font-semibold tracking-tight text-foreground sm:text-lg">Immich Dog Tagger</h1>
            <p className="hidden truncate text-xs text-muted-foreground sm:block sm:text-sm">Local dog recognition for your Immich library</p>
          </div>
        </div>

        <div className="flex flex-shrink-0 items-center gap-2 sm:gap-3">
          <nav className="flex gap-1 rounded-full border border-black/10 bg-background/70 p-1 shadow-sm dark:border-white/10 sm:gap-2">
            {links.map((link) => (
              <button
                key={link.path}
                type="button"
                className={
                  currentPath === link.path
                    ? "rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground sm:px-3 sm:py-1.5 sm:text-sm"
                    : "rounded-full px-2.5 py-1 text-xs text-muted-foreground sm:px-3 sm:py-1.5 sm:text-sm"
                }
                onClick={() => onNavigate(link.path)}
              >
                <span className="sm:hidden">{link.shortLabel}</span>
                <span className="hidden sm:inline">{link.label}</span>
              </button>
            ))}
          </nav>

          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}