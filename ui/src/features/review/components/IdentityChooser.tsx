import { IconArrowRight } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  identities: string[];
  species?: string;
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled?: boolean;
}

export function IdentityChooser({
  identities,
  species,
  onCorrect,
  onSkip,
  disabled,
}: Props) {
  const speciesLabel = species === "cat" ? "cats" : "dogs";
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Choose identity
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        {identities.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {identities.map((identity) => (
              <Button
                key={identity}
                onClick={() => onCorrect(identity)}
                disabled={disabled}
              >
                {identity}
              </Button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No {speciesLabel} are configured yet. Add one on the Dogs & Cats page before correcting reviews.
          </p>
        )}

        <Button
          variant="outline"
          onClick={onSkip}
          disabled={disabled}
        >
          <IconArrowRight className="h-4 w-4" aria-hidden="true" />
          Skip
        </Button>
      </CardContent>
    </Card>
  );
}