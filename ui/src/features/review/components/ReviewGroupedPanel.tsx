import { useCallback, useEffect, useState } from "react";

import { IconRefresh } from "@tabler/icons-react";

import { approveCluster, getReviewGroups, rejectCluster } from "../../../lib/api";
import type { ReviewGroup } from "../../../types/clusters";
import type { Dog } from "../../../types/dogs";

import { Button } from "@/components/ui/button";
import { ReviewGroupCard } from "./ReviewGroupCard";
import { ReviewGroupSplitView } from "./ReviewGroupSplitView";
import { ReviewSkeleton } from "./ReviewSkeleton";

interface Props {
  dogs: Dog[];
  immichUrl: string | null;
  /** Refreshes the Review tab's lifetime `reviewed` stat (and its milestone
   * celebration) after a group settles -- the same call site Queue mode
   * uses, so the two modes advance the same counters identically. */
  onReviewed: () => void;
}

/**
 * A group's identity can collide across different pets clustered in the
 * same request (a cluster's id is its lowest member's classification id,
 * and the same classification can appear in more than one pet's pool as a
 * runner-up candidate), so groups are keyed by identity+species+cluster id
 * together, never the cluster id alone.
 */
function groupKey(group: ReviewGroup): string {
  return `${group.species}:${group.identity}:${group.cluster.id}`;
}

export function ReviewGroupedPanel({ dogs, immichUrl, onReviewed }: Props) {
  const [groups, setGroups] = useState<ReviewGroup[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [splitGroup, setSplitGroup] = useState<ReviewGroup | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const proposal = await getReviewGroups();
      setGroups(proposal.groups);
      setTruncated(proposal.truncated_identities);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review groups");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const approve = async (group: ReviewGroup, classificationIds: number[]) => {
    setBusy(true);
    setActionMessage(null);

    try {
      const result = await approveCluster(group.identity, group.species, classificationIds);

      setActionMessage(
        result.skipped > 0
          ? `Approved ${result.applied} as ${group.identity}, skipped ${result.skipped} (already settled elsewhere).`
          : `Approved ${result.applied} as ${group.identity}.`,
      );

      onReviewed();
      await load();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Failed to approve group");
    } finally {
      setBusy(false);
    }
  };

  const reject = async (group: ReviewGroup, classificationIds: number[]) => {
    setBusy(true);
    setActionMessage(null);

    try {
      const result = await rejectCluster(group.identity, group.species, classificationIds);

      setActionMessage(`Recorded "not ${group.identity}" for ${result.applied} photo(s).`);

      await load();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Failed to reject group");
    } finally {
      setBusy(false);
    }
  };

  if (splitGroup) {
    return (
      <ReviewGroupSplitView
        group={splitGroup}
        dogs={dogs}
        immichUrl={immichUrl}
        onReviewed={onReviewed}
        onDone={() => {
          setSplitGroup(null);
          load();
        }}
      />
    );
  }

  if (loading) {
    return <ReviewSkeleton />;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-destructive">{error}</p>
        <Button onClick={() => load()}>
          <IconRefresh className="h-4 w-4" aria-hidden="true" />
          Retry
        </Button>
      </div>
    );
  }

  if (!groups || groups.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No batches of similar photos to review right now. Items without a predicted
        identity still need the regular Queue view.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {truncated && (
        <p className="text-sm text-muted-foreground">
          Showing groups for the identities with the most pending work; more remain and
          will appear as these are settled.
        </p>
      )}

      {actionMessage && <p className="text-sm text-muted-foreground">{actionMessage}</p>}

      {groups.map((group) => (
        <ReviewGroupCard
          key={groupKey(group)}
          group={group}
          disabled={busy}
          onApprove={(ids) => approve(group, ids)}
          onReject={(ids) => reject(group, ids)}
          onSplit={() => setSplitGroup(group)}
        />
      ))}
    </div>
  );
}
