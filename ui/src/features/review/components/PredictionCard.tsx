import { IconCheck } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ReviewCandidate } from "@/types/review";

interface Props {
  identity: string | null;
  similarity: number;
  candidates: ReviewCandidate[];
  onCorrect: (identity: string) => void;
  disabled?: boolean;
}

function confidenceLabel(similarity: number): string {
  if (similarity >= 0.85) {
    return "High confidence";
  }

  if (similarity >= 0.7) {
    return "Medium confidence";
  }

  return "Low confidence";
}

export function PredictionCard({
  identity,
  similarity,
  candidates,
  onCorrect,
  disabled,
}: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Prediction
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="text-2xl font-semibold">
          {identity ?? "Unknown"}
        </div>

        <div className="flex items-center gap-2">
          <Badge>
            {confidenceLabel(similarity)}
          </Badge>

          <span className="text-sm text-muted-foreground">
            {(similarity * 100).toFixed(1)}%
          </span>
        </div>

        {candidates.length > 1 && (
          <div className="space-y-2 pt-3">
            <div className="text-sm font-medium">
              Alternatives
            </div>

            {candidates.map((candidate) => (
              <div
                key={candidate.identity}
                className="flex items-center justify-between text-sm"
              >
                <div>
                  <span>
                    {candidate.identity}
                  </span>

                  <span className="ml-2 text-muted-foreground">
                    {(candidate.similarity * 100).toFixed(1)}%
                  </span>
                </div>

                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onCorrect(candidate.identity)}
                  disabled={disabled}
                >
                  <IconCheck className="h-4 w-4" aria-hidden="true" />
                  Correct
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}