import type { ReactNode } from "react";

import { Header } from "./Header";

interface Props {
  children: ReactNode;
}

export function AppShell({ children }: Props) {
  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto max-w-6xl p-6">
        {children}
      </main>
    </div>
  );
}