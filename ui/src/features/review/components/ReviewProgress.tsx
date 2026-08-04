import { Progress } from "@/components/ui/progress";

interface Props {
  reviewed: number;
  total: number;
  remaining: number;
}

export function ReviewProgress({
  reviewed,
  total,
  remaining,
}: Props) {
  const value =
    total === 0
      ? 0
      : (reviewed / total) * 100;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span>
          Reviewed {reviewed} / {total}
        </span>

        <span>
          {remaining} remaining
        </span>
      </div>

      <Progress value={value} />
    </div>
  );
}