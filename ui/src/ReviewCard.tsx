import type { ReviewItem } from "./types";

interface Props {
  item: ReviewItem;
  onCorrect: (identity: string) => void;
  onSkip: () => void;
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
  onSkip,
}: Props) {
  return (
    <section>
      <img
        src={`/api/crops/${item.crop_id}`}
        alt="dog crop"
        width={500}
      />

      <h2>Prediction</h2>

      <p>
        Identity:{" "}
        {item.prediction.identity ?? "Unknown"}
      </p>

      <p>
        Similarity:{" "}
        {item.prediction.similarity.toFixed(3)}
      </p>

      {item.suggestion && (
        <>
          <h2>Suggested Match</h2>

          <p>
            Identity: {item.suggestion.identity}
          </p>

          <p>
            Similarity:{" "}
            {item.suggestion.similarity.toFixed(3)}
          </p>

          <img
            src={`/api/embedding-examples/${item.suggestion.example_id}/image`}
            alt="matched example"
            width={250}
          />
        </>
      )}

      <h2>Correct Identity</h2>

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

      <button onClick={onSkip}>
        Skip
      </button>
    </section>
  );
}