import { Card, CardContent, CardHeader } from "@/components/ui/card";

function SkeletonRow() {
  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="h-4 w-40 rounded bg-muted" />
        <div className="h-5 w-16 rounded bg-muted" />
      </div>
      <div className="mt-3 h-3 w-full rounded bg-muted" />
    </div>
  );
}

function SkeletonSection({ rows }: { rows: number }) {
  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="h-5 w-24 rounded bg-muted" />
        <div className="h-3 w-32 rounded bg-muted" />
      </CardHeader>
      <CardContent className="space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <SkeletonRow key={index} />
        ))}
      </CardContent>
    </Card>
  );
}

export function JobQueueSkeleton() {
  return (
    <div className="animate-pulse space-y-6" aria-hidden="true">
      <SkeletonSection rows={2} />
      <SkeletonSection rows={1} />
      <SkeletonSection rows={3} />
    </div>
  );
}
