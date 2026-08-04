import { ThemeToggle } from "../theme/ThemeToggle";

export function Header() {
  return (
    <header className="flex items-center justify-between border-b p-4">
      <h1 className="text-xl font-semibold">
        🐾 Immich Dog Tagger
      </h1>

      <ThemeToggle />
    </header>
  );
}