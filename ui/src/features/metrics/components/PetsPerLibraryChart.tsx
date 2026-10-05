import type { LibraryPetCounts } from "../../../types/metrics";

interface Props {
  libraries: LibraryPetCounts[];
}

const SPECIES = [
  { key: "dogs", label: "Dogs", colorVar: "var(--chart-1)" },
  { key: "cats", label: "Cats", colorVar: "var(--chart-4)" },
] as const;

export function PetsPerLibraryChart({ libraries }: Props) {
  const largestTotal = Math.max(...libraries.map((item) => item.dogs_detected + item.cats_detected), 1);

  return (
    <div className="space-y-4">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground" aria-label="Legend">
        {SPECIES.map((species) => (
          <li key={species.key} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: species.colorVar }}
              aria-hidden="true"
            />
            {species.label}
          </li>
        ))}
      </ul>

      <ul className="space-y-3">
        {libraries.map((item) => {
          const counts = {
            dogs: { detected: item.dogs_detected, identified: item.dogs_identified },
            cats: { detected: item.cats_detected, identified: item.cats_identified },
          };
          const total = counts.dogs.detected + counts.cats.detected;

          return (
            <li key={item.library} className="space-y-1">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-medium">{item.library}</span>
                <span className="text-muted-foreground tabular-nums">
                  {counts.dogs.detected} dogs ({counts.dogs.identified} identified) · {counts.cats.detected} cats (
                  {counts.cats.identified} identified)
                </span>
              </div>
              <div
                role="img"
                aria-label={`${item.library}: ${counts.dogs.detected} dogs, ${counts.cats.detected} cats`}
                className="flex h-3 overflow-hidden rounded-full bg-border"
                style={{ width: `${(total / largestTotal) * 100}%`, minWidth: "0.75rem" }}
              >
                {SPECIES.map((species) => {
                  const detected = counts[species.key].detected;
                  if (detected === 0) return null;
                  return (
                    <div
                      key={species.key}
                      title={`${species.label}: ${detected}`}
                      style={{ width: `${(detected / total) * 100}%`, backgroundColor: species.colorVar }}
                    />
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
