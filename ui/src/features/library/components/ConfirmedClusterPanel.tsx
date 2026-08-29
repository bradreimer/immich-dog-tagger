import { useCallback, useEffect, useState } from "react";

import { IconRefresh } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { getConfirmedClusters, moveConfirmedPhotos } from "@/lib/api";
import type { ClusterProposal, ClusterSort } from "@/types/clusters";
import type { Dog } from "@/types/dogs";
import { CLUSTER_SORT_OPTIONS, DEFAULT_CLUSTER_SORT } from "../clusterSortOptions";
import { ClusterCard } from "./ClusterCard";

interface Props {
  identity: string;
  species: string;
  /** Active pets, both species -- filtered here to the move options each card offers. */
  identities?: Dog[];
  /** Called after a move lands, so the page can refresh what it shows. */
  onMoved?: (applied: number) => void;
}

/**
 * The confirmed-photo half of the Library workspace (v1.10, issue #183):
 * the selected pet's already-confirmed photos, grouped into clusters of
 * visually similar crops, with the same select-a-photo-or-a-group flow
 * `ClusterPanel` gives pending recommendations -- but the only action here
 * is moving the selection to a different pet. Approve/reject don't apply
 * to a photo already confirmed, so `ClusterCard` renders with neither.
 */
export function ConfirmedClusterPanel({
  identity,
  species,
  identities = [],
  onMoved,
}: Props) {
  const [proposal, setProposal] = useState<ClusterProposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sort, setSort] = useState<ClusterSort>(DEFAULT_CLUSTER_SORT);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setProposal(await getConfirmedClusters(identity, species, sort));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load confirmed photos");
    } finally {
      setLoading(false);
    }
  }, [identity, species, sort]);

  useEffect(() => {
    setNotice(null);
    load();
  }, [load]);

  const move = useCallback(
    async (targetIdentity: string, classificationIds: number[]) => {
      // The ids the owner left selected, passed explicitly -- same contract
      // as approve()/reassign(): the server never re-derives cluster
      // membership from a cluster id.
      const result = await moveConfirmedPhotos(
        identity,
        targetIdentity,
        species,
        classificationIds,
      );

      const skipped = result.skips
        .map((skip) => skip.reason)
        .filter((reason, index, reasons) => reasons.indexOf(reason) === index)
        .join(", ");

      setNotice(
        result.skipped === 0
          ? `Moved ${result.applied} ${result.applied === 1 ? "photo" : "photos"} to ${targetIdentity}.`
          : `Moved ${result.applied} of ${result.applied + result.skipped} photos to ${targetIdentity}. Skipped ${result.skipped}: ${skipped}.`,
      );

      onMoved?.(result.applied);

      await load();
    },
    [identity, species, onMoved, load],
  );

  // Same rule as the pending panel's reassignment picker: active pets of
  // this cluster's species, excluding the pet already selected here.
  const otherPets = identities.filter(
    (pet) => pet.species === species && pet.name !== identity,
  );

  return (
    <section className="space-y-4" aria-label={`Confirmed photos of ${identity}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Confirmed photos of {identity}
        </h2>

        {proposal && proposal.clusters.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {proposal.clustered_count} confirmed{" "}
            {proposal.clustered_count === 1 ? "photo" : "photos"} in{" "}
            {proposal.clusters.length}{" "}
            {proposal.clusters.length === 1 ? "group" : "groups"}
          </p>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        Sort
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value as ClusterSort)}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {CLUSTER_SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {notice && <p className="text-sm text-muted-foreground">{notice}</p>}

      {error && (
        <div className="space-y-3">
          <p className="text-sm text-destructive">{error}</p>
          <Button onClick={() => load()}>
            <IconRefresh className="h-4 w-4" aria-hidden="true" />
            Retry
          </Button>
        </div>
      )}

      {!error && loading && (
        <p className="text-sm text-muted-foreground">Grouping confirmed photos…</p>
      )}

      {!error && !loading && proposal && proposal.clusters.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No confirmed photos for {identity} yet. Photos appear here once an
          approval, a correction, or a review settles them as {identity}.
        </p>
      )}

      {!error && !loading && proposal && proposal.clusters.length > 0 && (
        <div className="space-y-4">
          {proposal.clusters.map((cluster) => (
            <ClusterCard
              key={`${identity}-confirmed-${cluster.id}`}
              cluster={cluster}
              identity={identity}
              otherPets={otherPets}
              onReassign={move}
              reassignPrompt="Move to"
              reassignVerb="Move"
              reassignBusyLabel="Moving…"
              representativeAlt={`Most representative photo of this group of ${identity}'s confirmed photos`}
            />
          ))}
        </div>
      )}

      {!error && !loading && proposal && proposal.excluded.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {proposal.excluded.length}{" "}
          {proposal.excluded.length === 1 ? "photo has" : "photos have"} no stored
          embedding and could not be grouped.
        </p>
      )}

      {!error && !loading && proposal?.truncated && (
        <p className="text-sm text-muted-foreground">
          Showing the strongest {proposal.candidate_count} confirmed photos; more
          appear once these are moved or the pool otherwise shrinks.
        </p>
      )}
    </section>
  );
}
