interface Props {
  onCorrect: (identity: string) => void;
  onSkip: () => void;
}

const identities = [
  "Fibs",
  "Hermann",
  "Henri",
  "Unknown",
];

export function IdentityChooser({
  onCorrect,
  onSkip,
}: Props) {
  return (
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
  );
}