import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
    <Card>
      <CardHeader>
        <CardTitle>
          Similar memory
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <img
          src={`/api/embedding-examples/${exampleId}/image`}
          alt={`Similar example of ${identity}`}
          className="w-full rounded-lg object-contain"
        />

        <div className="flex items-center justify-between">
          <span className="font-medium">
            {identity}
          </span>

          <Badge variant="secondary">
            {(similarity * 100).toFixed(1)}%
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}