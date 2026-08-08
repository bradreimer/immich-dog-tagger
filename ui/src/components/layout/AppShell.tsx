import type { ReactNode } from "react";

import { Header } from "./Header";

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
    <div className="min-h-screen">
      <Header currentPath={currentPath} onNavigate={onNavigate} />

      <main className="mx-auto max-w-6xl p-6">
        {children}
      </main>
    </div>
  );
}