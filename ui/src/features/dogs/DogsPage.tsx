import { DogManagementCard } from "./components/DogManagementCard";

interface Props {
  onNavigate: (path: string) => void;
}

export function DogsPage({ onNavigate }: Props) {
  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Dogs & Cats</h1>
        <p className="text-muted-foreground">
          Manage the dog and cat identities used by review and learning.
        </p>
      </header>

      <DogManagementCard onNavigate={onNavigate} />
    </section>
  );
}
