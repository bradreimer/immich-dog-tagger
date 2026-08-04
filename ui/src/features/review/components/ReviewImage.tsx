interface Props {
  cropId: number;
}

export function ReviewImage({ cropId }: Props) {
  return (
    <img
      src={`/api/crops/${cropId}`}
      alt="dog crop"
      className="max-h-[70vh] rounded-lg object-contain"
    />
  );
}