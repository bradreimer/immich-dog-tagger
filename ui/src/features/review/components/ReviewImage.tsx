import { Card } from "@/components/ui/card";

interface Props {
  cropId: number;
}

export function ReviewImage({ cropId }: Props) {
  return (
    <Card className="flex items-center justify-center overflow-hidden p-4">
      <img
        src={`/api/crops/${cropId}`}
        alt="dog crop"
        className="max-h-[70vh] max-w-full rounded-lg object-contain"
      />
    </Card>
  );
}