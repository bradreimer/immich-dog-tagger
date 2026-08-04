import { Card } from "@/components/ui/card";

export function ReviewSkeleton() {
  return (
    <Card className="space-y-6 p-6 animate-pulse">
      <div className="h-[50vh] rounded-lg bg-muted" />

      <div className="h-8 w-48 rounded bg-muted" />

      <div className="h-4 w-64 rounded bg-muted" />

      <div className="flex gap-3">
        <div className="h-10 w-24 rounded bg-muted" />
        <div className="h-10 w-24 rounded bg-muted" />
      </div>
    </Card>
  );
}