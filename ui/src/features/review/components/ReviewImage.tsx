import { Card } from "@/components/ui/card";

interface Props {
  cropId: number;
  species: string;
}

export function ReviewImage({ cropId, species }: Props) {
  return (
    <Card className="flex items-center justify-center overflow-hidden p-4 lg:h-full">
      <img
        src={`/api/crops/${cropId}`}
        alt={`${species} crop`}
        className="
          max-h-[70vh]
          w-full
          rounded-xl
          object-contain
          transition-all
          duration-300
          lg:h-full
          lg:max-h-none
        "
      />
    </Card>
  );
}