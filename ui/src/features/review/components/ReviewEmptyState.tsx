import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface Props {
  onRefresh: () => void;
}

export function ReviewEmptyState({
  onRefresh,
}: Props) {
  return (
    <Card className="space-y-4 p-8 text-center">
      <h2 className="text-2xl font-semibold">
        Review complete 🐾
      </h2>

      <p className="text-muted-foreground">
        No classifications need attention right now.
      </p>

      <Button onClick={onRefresh}>
        Refresh queue
      </Button>
    </Card>
  );
}