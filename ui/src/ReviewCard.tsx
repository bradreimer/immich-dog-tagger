import type { ReviewItem } from "./types";

interface Props {
  item: ReviewItem;
  onCorrect: (identity: string) => void;
}

const identities = [
  "Fibs",
  "Hermann",
  "Henri",
  "Unknown",
];

export function ReviewCard({
  item,
  onCorrect,
}: Props) {
  return (
    <section>
      <img
        src={`/api/crops/${item.crop_id}`}
        alt="dog crop"
        width={400}
      />

      <p>
        Prediction: {item.identity ?? "Unknown"}
      </p>

      <p>
        Confidence: {(item.confidence * 100).toFixed(1)}%
      </p>

      <div>
        {identities.map((identity) => (
          <button
            key={identity}
            onClick={() => onCorrect(identity)}
          >
            {identity}
          </button>
        ))}
      </div>
    </section>
  );
}