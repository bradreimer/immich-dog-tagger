import { DogManagementCard } from "./components/DogManagementCard";

export function DogsPage() {
  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Dogs & Cats</h1>
        <p className="text-muted-foreground">
          Manage the dog and cat identities used by review and learning.
        </p>
      </header>

      <DogManagementCard />
    </section>
  );
}
