import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled?: boolean;
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
  disabled,
}: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Choose identity
        </CardTitle>
      </CardHeader>

      <CardContent className="flex flex-wrap gap-2">
        {identities.map((identity) => (
          <Button
            key={identity}
            onClick={() => onCorrect(identity)}
            disabled={disabled}
          >
            {identity}
          </Button>
        ))}

        <Button
          variant="outline"
          onClick={onSkip}
          disabled={disabled}
        >
          Skip
        </Button>
      </CardContent>
    </Card>
  );
}