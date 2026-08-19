import { useState } from "react";

import { IconCheck, IconPhoto } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { RecommendationCluster } from "@/types/clusters";

/** How many member thumbnails to show before collapsing the rest into a count. */
const VISIBLE_MEMBERS = 11;

function similarityRange(cluster: RecommendationCluster): string {
  const low = (cluster.min_similarity * 100).toFixed(0);
  const high = (cluster.max_similarity * 100).toFixed(0);

  return low === high ? `${low}% confidence` : `${low}-${high}% confidence`;
}

function captureRange(cluster: RecommendationCluster): string {
  if (!cluster.earliest_captured_at && !cluster.latest_captured_at) {
    return "Dates unknown";
  }

  const earliest = formatDate(cluster.earliest_captured_at);
  const latest = formatDate(cluster.latest_captured_at);

  return earliest === latest ? earliest : `${earliest} – ${latest}`;
}

interface Props {
  cluster: RecommendationCluster;
  identity: string;
  onApprove: (cluster: RecommendationCluster) => Promise<void>;
}

export function ClusterCard({ cluster, identity, onApprove }: Props) {
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hidden = Math.max(0, cluster.members.length - VISIBLE_MEMBERS);
  const visible = cluster.members.slice(0, VISIBLE_MEMBERS);

  const handleApprove = async () => {
    setError(null);
    setApproving(true);

    try {
      await onApprove(cluster);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve");
    } finally {
      setApproving(false);
    }
  };

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-start gap-4">
          <img
            src={`/api/crops/${cluster.representative.crop_id}`}
            alt={`Most representative photo of this group of ${identity} recommendations`}
            className="h-28 w-28 shrink-0 rounded-lg object-cover"
          />

          <div className="min-w-48 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">
                {cluster.size} {cluster.size === 1 ? "photo" : "photos"}
              </span>

              <Badge variant="outline">{similarityRange(cluster)}</Badge>
            </div>

            <p className="text-sm text-muted-foreground">{captureRange(cluster)}</p>

            <Button
              type="button"
              onClick={handleApprove}
              disabled={approving}
              aria-label={`Approve ${cluster.size} photos as ${identity}`}
            >
              <IconCheck className="h-4 w-4" aria-hidden="true" />
              {approving
                ? "Approving…"
                : `Approve all as ${identity}`}
            </Button>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {visible.map((member) => (
            <img
              key={member.classification_id}
              src={`/api/crops/${member.crop_id}`}
              alt={member.filename}
              title={formatDate(member.captured_at)}
              className="h-14 w-14 rounded-md object-cover"
            />
          ))}

          {hidden > 0 && (
            <span className="flex h-14 w-14 items-center justify-center gap-1 rounded-md bg-muted text-xs text-muted-foreground">
              <IconPhoto className="h-3 w-3" aria-hidden="true" />+{hidden}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
