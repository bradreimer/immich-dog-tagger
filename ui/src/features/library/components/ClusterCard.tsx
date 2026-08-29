import { useState } from "react";

import { IconArrowsRightLeft, IconCheck, IconPhoto, IconX } from "@tabler/icons-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useSelection } from "@/hooks/useSelection";
import { formatDate } from "@/lib/utils";
import type { RecommendationCluster } from "@/types/clusters";
import type { Dog } from "@/types/dogs";

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
  /**
   * Approve/reject only apply to a *pending* cluster (issues #141/#144).
   * Omitting both turns this into a plain selectable cluster with only the
   * reassignment control -- the shape v1.10's confirmed-photo view needs,
   * without a second cluster-card component to keep visually in sync.
   */
  onApprove?: (classificationIds: number[]) => Promise<void>;
  onReject?: (classificationIds: number[]) => Promise<void>;
  /** Other pets of this cluster's species the selection can be reassigned to (issue #166). */
  otherPets?: Dog[];
  onReassign?: (identity: string, classificationIds: number[]) => Promise<void>;
  /** Copy in front of the reassignment picker. Defaults to the pending-cluster wording. */
  reassignPrompt?: string;
  /** Verb used on the reassignment button and its aria-label ("Assign"/"Move"). */
  reassignVerb?: string;
  /** Label shown on the reassignment button while the request is in flight. */
  reassignBusyLabel?: string;
  /** Alt text for the representative thumbnail. Defaults to the pending-cluster wording. */
  representativeAlt?: string;
}

export function ClusterCard({
  cluster,
  identity,
  onApprove,
  onReject,
  otherPets = [],
  onReassign,
  reassignPrompt = `Not ${identity}? Assign to`,
  reassignVerb = "Assign",
  reassignBusyLabel = "Assigning…",
  representativeAlt = `Most representative photo of this group of ${identity} recommendations`,
}: Props) {
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reassigning, setReassigning] = useState(false);
  const [reassignTarget, setReassignTarget] = useState("");
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
    if (!onApprove) {
      return;
    }

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
    if (!onReject) {
      return;
    }

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

  const handleReassign = async () => {
    if (!reassignTarget || !onReassign) {
      return;
    }

    setError(null);
    setReassigning(true);

    try {
      await onReassign(reassignTarget, selection.selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reassign");
    } finally {
      setReassigning(false);
    }
  };

  const busy = approving || rejecting || reassigning;

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-start gap-4">
          <img
            src={`/api/crops/${cluster.representative.crop_id}`}
            alt={representativeAlt}
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

            {(onApprove || onReject) && (
              <div className="flex flex-wrap items-center gap-2">
                {onApprove && (
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
                )}

                {onReject && (
                  // Outline rather than the filled action treatment:
                  // rejecting is a correction, not the primary path through
                  // this card, and it must not read as a second way to say
                  // yes.
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
                )}
              </div>
            )}

            {/*
              A third path alongside Approve/Not <identity> (issue #166): the
              group is correctly clustered as one animal, but it is not this
              pet. Picking another pet settles the selection directly instead
              of rejecting it back into the pending queue and hoping the
              right pet gets recommended for it later.
            */}
            {otherPets.length > 0 && (
              <div
                className="flex flex-wrap items-center gap-2"
                role="group"
                aria-label={`${reassignVerb} ${photos(selection.selectedCount)} to a different pet`}
              >
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  {reassignPrompt}
                  <select
                    value={reassignTarget}
                    onChange={(event) => setReassignTarget(event.target.value)}
                    disabled={busy}
                    className="h-9 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <option value="">Select another pet…</option>
                    {otherPets.map((pet) => (
                      <option key={pet.id} value={pet.name}>
                        {pet.name}
                      </option>
                    ))}
                  </select>
                </label>

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleReassign}
                  disabled={busy || selection.noneSelected || !reassignTarget}
                  aria-label={`${reassignVerb} ${photos(selection.selectedCount)} to ${
                    reassignTarget || "another pet"
                  }`}
                >
                  <IconArrowsRightLeft className="h-4 w-4" aria-hidden="true" />
                  {reassigning ? reassignBusyLabel : reassignVerb}
                </Button>
              </div>
            )}

            {selection.noneSelected && (
              <p className="text-sm text-muted-foreground">
                Select at least one photo to{" "}
                {[
                  onApprove && "approve",
                  onReject && "reject",
                  onReassign && reassignVerb.toLowerCase(),
                ]
                  .filter(Boolean)
                  .join(" or ")}
                .
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
