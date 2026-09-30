import { useCallback, useEffect, useState } from "react";

import { IconArrowLeft, IconArrowRight, IconRefresh } from "@tabler/icons-react";

import {
  ClassificationNotFoundError,
  CropNotFoundError,
  approveCluster,
  correctSpecies,
  getReviewGroups,
  markCropNotAnimal,
  reassignCluster,
  rejectCluster,
  skipClassification,
} from "../../../lib/api";
import type { ReviewGroup } from "../../../types/clusters";
import type { Dog } from "../../../types/dogs";

import { Button } from "@/components/ui/button";
import { ReviewGroupCard } from "./ReviewGroupCard";
import { ReviewGroupSplitView } from "./ReviewGroupSplitView";
import { ReviewSkeleton } from "./ReviewSkeleton";

interface Props {
  dogs: Dog[];
  immichUrl: string | null;
  showAccount?: boolean;
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

export function ReviewGroupedPanel({
  dogs,
  immichUrl,
  showAccount = false,
  onReviewed,
}: Props) {
  const [groups, setGroups] = useState<ReviewGroup[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [splitGroup, setSplitGroup] = useState<ReviewGroup | null>(null);
  // Position in `groups`, kept across refetches: once the group at this
  // position settles and drops out of the list, the same index shows the
  // next one.
  const [index, setIndex] = useState(0);
  // Bumped on every refetch so a partially settled group remounts with a
  // fresh default selection instead of keeping ids that no longer exist.
  const [generation, setGeneration] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const proposal = await getReviewGroups();
      setGroups(proposal.groups);
      setTruncated(proposal.truncated_identities);
      setGeneration((current) => current + 1);
      setIndex((current) => Math.max(0, Math.min(current, proposal.groups.length - 1)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review groups");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /**
   * Runs one settling action, reports its outcome, and refetches so the
   * settled group drops out of the list. `countsAsReviewed` is false only
   * for "Not <identity>", which settles no identity (parent spec FR-7).
   */
  const run = async (
    action: () => Promise<string>,
    failure: string,
    countsAsReviewed = true,
  ) => {
    setBusy(true);
    setActionMessage(null);

    try {
      setActionMessage(await action());

      if (countsAsReviewed) {
        onReviewed();
      }

      await load();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : failure);
    } finally {
      setBusy(false);
    }
  };

  /**
   * Applies a per-photo write to every selected member in turn. A member
   * whose classification/crop was deleted server-side (a Repair elsewhere
   * reprocessed the photo while this group was loaded) is counted as
   * skipped rather than failing the whole batch -- the same handling the
   * split view gives a stale item (issue #356).
   */
  const eachMember = async (
    classificationIds: number[],
    write: (classificationId: number) => Promise<unknown>,
  ) => {
    let applied = 0;
    let skipped = 0;

    for (const classificationId of classificationIds) {
      try {
        await write(classificationId);
        applied += 1;
      } catch (err) {
        if (err instanceof ClassificationNotFoundError || err instanceof CropNotFoundError) {
          skipped += 1;
          continue;
        }

        throw err;
      }
    }

    return { applied, skipped };
  };

  const summarize = (summary: string, skipped: number) =>
    skipped > 0 ? `${summary}, skipped ${skipped} (already settled elsewhere).` : `${summary}.`;

  /**
   * Choosing the group's own identity is an approval of what the
   * classifier proposed; choosing any other identity is a reassignment
   * (issue #166), since not every member's own candidate list is
   * guaranteed to include it.
   */
  const chooseIdentity = (group: ReviewGroup, identity: string, classificationIds: number[]) =>
    run(async () => {
      const settle = identity === group.identity ? approveCluster : reassignCluster;
      const result = await settle(identity, group.species, classificationIds);
      return summarize(`Approved ${result.applied} as ${identity}`, result.skipped);
    }, "Failed to approve group");

  const reject = (group: ReviewGroup, classificationIds: number[]) =>
    run(
      async () => {
        const result = await rejectCluster(group.identity, group.species, classificationIds);
        return `Recorded "not ${group.identity}" for ${result.applied} photo(s).`;
      },
      "Failed to reject group",
      false,
    );

  const skip = (classificationIds: number[]) =>
    run(async () => {
      const { applied, skipped } = await eachMember(classificationIds, skipClassification);
      return summarize(`Skipped ${applied}`, skipped);
    }, "Failed to save skip action");

  const correctSpeciesForGroup = (species: "dog" | "cat", classificationIds: number[]) =>
    run(async () => {
      const { applied, skipped } = await eachMember(classificationIds, (id) =>
        correctSpecies(id, species),
      );
      return summarize(`Changed ${applied} to ${species}`, skipped);
    }, "Failed to correct species");

  const markNotAnimal = (group: ReviewGroup, classificationIds: number[]) =>
    run(async () => {
      const cropByClassification = new Map(
        group.cluster.members.map((member) => [member.classification_id, member.crop_id]),
      );
      const { applied, skipped } = await eachMember(classificationIds, (id) => {
        const cropId = cropByClassification.get(id);
        return cropId === undefined ? Promise.resolve() : markCropNotAnimal(cropId);
      });
      return summarize(`Marked ${applied} as not a dog or cat`, skipped);
    }, "Failed to update");

  if (splitGroup) {
    return (
      <ReviewGroupSplitView
        group={splitGroup}
        dogs={dogs}
        immichUrl={immichUrl}
        showAccount={showAccount}
        onReviewed={onReviewed}
        onDone={() => {
          setSplitGroup(null);
          load();
        }}
      />
    );
  }

  if (loading && !groups) {
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
      <div className="space-y-4">
        {actionMessage && <p className="text-sm text-muted-foreground">{actionMessage}</p>}
        <p className="text-sm text-muted-foreground">
          No batches of similar photos to review right now. Items without a predicted
          identity still need the regular Queue view.
        </p>
      </div>
    );
  }

  const group = groups[Math.min(index, groups.length - 1)];
  const position = groups.indexOf(group);
  const previous = () => {
    if (!busy) {
      setIndex(Math.max(0, position - 1));
    }
  };
  const next = () => {
    if (!busy) {
      setIndex(Math.min(groups.length - 1, position + 1));
    }
  };

  const identities = dogs
    .filter((dog) => dog.species === group.species)
    .map((dog) => dog.name);

  return (
    <div className="space-y-4">
      {truncated && (
        <p className="text-sm text-muted-foreground">
          Showing groups for the identities with the most pending work; more remain and
          will appear as these are settled.
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">
          Group {position + 1} of {groups.length}
        </span>

        <div className="flex gap-2">
          <Button variant="outline" onClick={previous} disabled={busy || position === 0}>
            <IconArrowLeft className="h-4 w-4" aria-hidden="true" />
            Previous group
          </Button>

          <Button
            variant="outline"
            onClick={next}
            disabled={busy || position === groups.length - 1}
          >
            Next group
            <IconArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {actionMessage && <p className="text-sm text-muted-foreground">{actionMessage}</p>}

      <ReviewGroupCard
        key={`${groupKey(group)}:${generation}`}
        group={group}
        identities={identities}
        disabled={busy || loading}
        onChooseIdentity={(identity, ids) => chooseIdentity(group, identity, ids)}
        onReject={(ids) => reject(group, ids)}
        onSkip={skip}
        onCorrectSpecies={correctSpeciesForGroup}
        onNotAnimal={(ids) => markNotAnimal(group, ids)}
        onSplit={() => setSplitGroup(group)}
        onNext={next}
        onPrevious={previous}
      />
    </div>
  );
}
