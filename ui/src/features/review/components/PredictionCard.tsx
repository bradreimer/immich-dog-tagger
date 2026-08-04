interface Props {
  identity: string | null;
  similarity: number;
}

export function PredictionCard({
  identity,
  similarity,
}: Props) {
  return (
    <section>
      <h3>
        Prediction
      </h3>

      <p className="text-xl font-semibold">
        {identity ?? "Unknown"}
      </p>

      <p>
        Similarity:
        {" "}
        {similarity.toFixed(3)}
      </p>
    </section>
  );
}