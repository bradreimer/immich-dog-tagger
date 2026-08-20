import { useState } from "react";

import { IconCheck, IconPhoto, IconX } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useSelection } from "@/hooks/useSelection";
import { formatDate } from "@/lib/utils";
import type { RecommendationCluster } from "@/types/clusters";

/** How many member thumbnails to show before collapsing the rest behind a toggle. */
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

function photos(count: number): string {
  return `${count} ${count === 1 ? "photo" : "photos"}`;
}

interface Props {
  cluster: RecommendationCluster;
  identity: string;
  onApprove: (classificationIds: number[]) => Promise<void>;
  onReject: (classificationIds: number[]) => Promise<void>;
}

export function ClusterCard({ cluster, identity, onApprove, onReject }: Props) {
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  // Every member starts selected; deselecting the odd photo that does not
  // belong is the exception path (issue #142). The hook resets whenever the
  // member ids change, so a selection never carries across pets.
  const selection = useSelection(
    cluster.members.map((member) => member.classification_id),
  );

  const hidden = Math.max(0, cluster.members.length - VISIBLE_MEMBERS);
  const visible =
    expanded || hidden === 0
      ? cluster.members
      : cluster.members.slice(0, VISIBLE_MEMBERS);

  const handleApprove = async () => {
    setError(null);
    setApproving(true);

    try {
      // The explicit selected list, never "the cluster": the server approves
      // exactly what it is given, so a deselected photo cannot be swept in by
      // membership re-derived server-side.
      await onApprove(selection.selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve");
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    setError(null);
    setRejecting(true);

    try {
      // Same selection, opposite sign (issue #144). Deselecting a photo
      // means "not now"; rejecting it means "this is not this pet", which
      // is recorded and stops the recommendation coming back.
      await onReject(selection.selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject");
    } finally {
      setRejecting(false);
    }
  };

  const busy = approving || rejecting;

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-start gap-4">
          <img
            src={`/api/crops/${cluster.representative.crop_id}`}
            alt={`Most representative photo of this group of ${identity} recommendations`}
            className="h-28 w-28 shrink-0 rounded-lg object-cover"
            loading="lazy"
            decoding="async"
          />

          <div className="min-w-48 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{photos(cluster.size)}</span>

              <Badge variant="outline">{similarityRange(cluster)}</Badge>
            </div>

            <p className="text-sm text-muted-foreground">{captureRange(cluster)}</p>

            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {selection.selectedCount} of {cluster.size} selected
              </p>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={selection.selectAll}
                disabled={selection.allSelected}
              >
                Select all
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={selection.selectNone}
                disabled={selection.noneSelected}
              >
                Select none
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                onClick={handleApprove}
                disabled={busy || selection.noneSelected}
                aria-label={`Approve ${photos(selection.selectedCount)} as ${identity}`}
              >
                <IconCheck className="h-4 w-4" aria-hidden="true" />
                {approving
                  ? "Approving…"
                  : `Approve ${photos(selection.selectedCount)}`}
              </Button>

              {/*
                Outline rather than the filled action treatment: rejecting is
                a correction, not the primary path through this card, and it
                must not read as a second way to say yes.
              */}
              <Button
                type="button"
                variant="outline"
                onClick={handleReject}
                disabled={busy || selection.noneSelected}
                aria-label={`Mark ${photos(selection.selectedCount)} as not ${identity}`}
              >
                <IconX className="h-4 w-4" aria-hidden="true" />
                {rejecting ? "Saving…" : `Not ${identity}`}
              </Button>
            </div>

            {selection.noneSelected && (
              <p className="text-sm text-muted-foreground">
                Select at least one photo to approve or reject.
              </p>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        </div>

        {/*
          Each member is a real toggle button, so Tab reaches it and Space or
          Enter flips it. Selection deliberately adds no global shortcut: the
          Review page's vocabulary (useReviewKeyboard.ts) is the app's one
          keymap, and a second one competing across several clusters on a page
          would be ambiguous about which cluster it meant.
        */}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Photos in this group">
          {visible.map((member) => {
            const selected = selection.isSelected(member.classification_id);

            return (
              <button
                key={member.classification_id}
                type="button"
                role="checkbox"
                aria-checked={selected}
                aria-label={member.filename}
                title={formatDate(member.captured_at)}
                onClick={() => selection.toggle(member.classification_id)}
                className={`relative h-14 w-14 overflow-hidden rounded-md border-2 transition-all focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                  selected
                    ? "border-primary"
                    : "border-primary/30 opacity-50 grayscale hover:opacity-75"
                }`}
              >
                <img
                  src={`/api/crops/${member.crop_id}`}
                  alt=""
                  className="h-full w-full object-cover"
                  loading="lazy"
                  decoding="async"
                />

                {selected && (
                  <span className="absolute right-0 bottom-0 flex h-4 w-4 items-center justify-center rounded-tl-md bg-primary text-primary-foreground">
                    <IconCheck className="h-3 w-3" aria-hidden="true" />
                  </span>
                )}
              </button>
            );
          })}

          {hidden > 0 && !expanded && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-14 w-14 flex-col gap-0.5 px-0 text-xs"
              onClick={() => setExpanded(true)}
              aria-label={`Show all ${photos(cluster.size)} in this group`}
            >
              <IconPhoto className="h-3 w-3" aria-hidden="true" />+{hidden}
            </Button>
          )}

          {hidden > 0 && expanded && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-14 px-3 text-xs"
              onClick={() => setExpanded(false)}
            >
              Show fewer
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
