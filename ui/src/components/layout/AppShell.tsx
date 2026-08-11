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

      <main className="min-w-0 flex-1 overflow-x-hidden bg-background p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
