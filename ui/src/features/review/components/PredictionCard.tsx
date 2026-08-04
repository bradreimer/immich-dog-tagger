import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  identity: string | null;
  similarity: number;
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
      </CardContent>
    </Card>
  );
}