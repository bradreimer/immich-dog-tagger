import type { ReviewItem } from "../../types/review";

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

function formatSimilarity(value: number): string {
  return value.toFixed(3);
}

export function ReviewCard({
  item,
  onCorrect,
  onSkip,
}: Props) {
  return (
    <section>
      <h2>
        Review Classification #{item.classification_id}
      </h2>

      <img
        src={`/api/crops/${item.crop_id}`}
        alt="dog crop"
        width={400}
      />

      <p>
        Crop ID: {item.crop_id}
      </p>

      <p>
        Prediction:
        {" "}
        <strong>
          {item.prediction.identity ?? "Unknown"}
        </strong>
      </p>

      <p>
        Prediction similarity:
        {" "}
        {formatSimilarity(item.prediction.similarity)}
      </p>

      {item.suggestion && (
        <aside>
          <h3>
            Model suggestion
          </h3>

          <p>
            Identity:
            {" "}
            <strong>
              {item.suggestion.identity}
            </strong>
          </p>

          <p>
            Similarity:
            {" "}
            {formatSimilarity(item.suggestion.similarity)}
          </p>

          <p>
            Example ID:
            {" "}
            {item.suggestion.example_id}
          </p>

          <img
            src={`/api/embedding-examples/${item.suggestion.example_id}/image`}
            alt="matched example"
            width={200}
          />
        </aside>
      )}

      <h3>
        Choose identity
      </h3>

      <div>
        {identities.map((identity) => (
          <button
            key={identity}
            onClick={() => onCorrect(identity)}
          >
            {identity}
          </button>
        ))}

        <button onClick={onSkip}>
          Skip
        </button>
      </div>
    </section>
  );
}