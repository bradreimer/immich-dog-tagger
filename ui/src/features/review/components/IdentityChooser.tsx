import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  identities: string[];
  onCorrect: (identity: string) => void;
  onSkip: () => void;
  disabled?: boolean;
}

export function IdentityChooser({
  identities,
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
            No dogs are configured yet. Add one in Mission Control before correcting reviews.
          </p>
        )}

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