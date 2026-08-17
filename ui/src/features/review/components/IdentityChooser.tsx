import { IconArrowRight, IconStarFilled } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  identities: string[];
  species?: string;
  predictedIdentity?: string | null;
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled?: boolean;
}

export function IdentityChooser({
  identities,
  species,
  predictedIdentity,
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
            {identities.map((identity) => {
              const isPredicted = identity === predictedIdentity;
              return (
                <Button
                  key={identity}
                  variant={isPredicted ? "default" : "outline"}
                  onClick={() => onCorrect(identity)}
                  disabled={disabled}
                  aria-label={isPredicted ? `${identity} (predicted)` : identity}
                >
                  {isPredicted && (
                    <IconStarFilled className="h-4 w-4" aria-hidden="true" />
                  )}
                  {identity}
                </Button>
              );
            })}
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