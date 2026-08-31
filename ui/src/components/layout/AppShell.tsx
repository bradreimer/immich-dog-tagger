import type { ReactNode } from "react";

import { Sidebar } from "./Sidebar";

interface Props {
  children: ReactNode;
  currentPath: string;
  onNavigate: (path: string) => void;
}

export function AppShell({
  children,
  currentPath,
  onNavigate,
}: Props) {
  return (
    <div className="flex min-h-screen">
      <Sidebar currentPath={currentPath} onNavigate={onNavigate} />

      {/* overflow-x-clip, not overflow-x-hidden: setting only overflow-x to a
          non-visible value makes the browser compute the unset overflow-y as
          "auto" too, turning `main` into a scroll container in its own right.
          Since `main` never actually scrolls (the window does), that silently
          breaks `position: sticky` for any descendant -- e.g. the Library
          page's details panel, which would just scroll away instead of
          staying pinned. `clip` doesn't carry that same-axis coupling. */}
      <main className="min-w-0 flex-1 overflow-x-clip bg-background p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
