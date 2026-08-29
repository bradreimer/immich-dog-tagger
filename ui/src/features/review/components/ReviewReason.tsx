import { Badge } from "@/components/ui/badge";

interface Props {
  reason: string;
}

function formatReason(reason: string): string {
  switch (reason) {
    case "unknown":
      return "Unknown identity";

    case "low-confidence":
      return "Low confidence";

    case "candidate-conflict":
      return "Candidate conflict";

    case "temporal-mismatch":
      return "Recency mismatch";

    case "location-mismatch":
      return "Location mismatch";

    default:
      return "Needs review";
  }
}

export function ReviewReason({ reason }: Props) {
  return (
    <Badge variant="outline">
      {formatReason(reason)}
    </Badge>
  );
}