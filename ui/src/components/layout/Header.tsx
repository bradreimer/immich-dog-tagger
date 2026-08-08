import { ThemeToggle } from "../theme/ThemeToggle";

interface Props {
  currentPath: string;
  onNavigate: (path: string) => void;
}

export function Header({ currentPath, onNavigate }: Props) {
  const links = [
    {
      label: "Mission Control",
      path: "/",
    },
    {
      label: "Job Queue",
      path: "/jobs",
    },
    {
      label: "Review",
      path: "/review",
    },
  ];

  return (
    <header className="border-b bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.2),_transparent_45%),linear-gradient(135deg,_rgba(255,255,255,0.95),_rgba(254,242,242,0.9))] backdrop-blur supports-[backdrop-filter]:bg-white/70 dark:bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.18),_transparent_45%),linear-gradient(135deg,_rgba(17,24,39,0.95),_rgba(31,41,55,0.9))]">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <img
            src="/banner.png"
            alt="Immich Dog Tagger"
            className="h-12 w-auto rounded-lg object-cover shadow-sm ring-1 ring-black/10 dark:ring-white/10"
          />
          <div className="space-y-1">
            <h1 className="text-lg font-semibold tracking-tight text-foreground">Immich Dog Tagger</h1>
            <p className="text-sm text-muted-foreground">Local dog recognition for your Immich library</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <nav className="flex gap-2 rounded-full border border-black/10 bg-background/70 p-1 shadow-sm dark:border-white/10">
            {links.map((link) => (
              <button
                key={link.path}
                type="button"
                className={
                  currentPath === link.path
                    ? "rounded-full bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
                    : "rounded-full px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                }
                onClick={() => onNavigate(link.path)}
              >
                {link.label}
              </button>
            ))}
          </nav>

          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}