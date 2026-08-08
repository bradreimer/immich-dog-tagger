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
      label: "Review",
      path: "/review",
    },
  ];

  return (
    <header className="flex items-center justify-between border-b p-4">
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">Immich Dog Tagger</h1>

        <nav className="flex gap-2 text-sm">
          {links.map((link) => (
            <button
              key={link.path}
              type="button"
              className={
                currentPath === link.path
                  ? "rounded border bg-secondary px-2 py-1"
                  : "rounded border px-2 py-1"
              }
              onClick={() => onNavigate(link.path)}
            >
              {link.label}
            </button>
          ))}
        </nav>
      </div>

      <ThemeToggle />
    </header>
  );
}