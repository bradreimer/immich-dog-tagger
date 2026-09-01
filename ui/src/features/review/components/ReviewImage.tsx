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
        className="
          max-h-[70vh]
          w-full
          rounded-xl
          object-contain
          transition-all
          duration-300
          lg:max-h-[58vh]
        "
      />
    </Card>
  );
}