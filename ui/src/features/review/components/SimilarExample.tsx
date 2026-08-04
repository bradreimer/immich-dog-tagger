interface Props {
  exampleId: number;
  identity: string;
  similarity: number;
}

export function SimilarExample({
  exampleId,
  identity,
  similarity,
}: Props) {
  return (
    <aside>
      <h3>
        Similar example
      </h3>

      <p>
        {identity}
        {" "}
        ({similarity.toFixed(3)})
      </p>

      <img
        src={`/api/embedding-examples/${exampleId}/image`}
        alt="similar example"
        width={200}
        className="rounded-lg"
      />
    </aside>
  );
}