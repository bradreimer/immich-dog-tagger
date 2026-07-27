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
        Prediction: {item.prediction.identity ?? "Unknown"}
      </p>

      <p>
        Similarity: {item.prediction.similarity.toFixed(3)}
        {item.suggestion && (
          <div>
            <p>
              Suggested: {item.suggestion.identity}
            </p>

            <p>
              Similarity: {item.suggestion.similarity.toFixed(3)}
            </p>

            <img
              src={`/api/examples/${item.suggestion.example_path}`}
              alt="suggested example"
              width={200}
            />
          </div>
        )}
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