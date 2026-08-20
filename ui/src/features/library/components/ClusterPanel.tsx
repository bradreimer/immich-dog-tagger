import { useCallback, useEffect, useState } from "react";

import { IconRefresh } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { approveCluster, getPetClusters, rejectCluster } from "@/lib/api";
import type { ClusterProposal, ClusterSort } from "@/types/clusters";
import { ClusterCard } from "./ClusterCard";

/**
 * The four orders issue #143 defines, in a fixed display order. Confidence
 * descending is the default -- approve the surest group first.
 */
const SORT_OPTIONS: { value: ClusterSort; label: string }[] = [
  { value: "confidence_desc", label: "Surest first" },
  { value: "confidence_asc", label: "Least sure first" },
  { value: "captured_desc", label: "Newest first" },
  { value: "captured_asc", label: "Oldest first" },
];

const DEFAULT_SORT: ClusterSort = "confidence_desc";

interface Props {
  identity: string;
  species: string;
  /** Called after an approval lands, so the page can refresh what it shows. */
  onApproved?: (applied: number) => void;
}

/**
 * The approval half of the Library workspace (issue #141): the pending
 * recommendations for the selected pet, grouped into clusters of visually
 * similar crops, each approvable in one action.
 */
export function ClusterPanel({ identity, species, onApproved }: Props) {
  const [proposal, setProposal] = useState<ClusterProposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sort, setSort] = useState<ClusterSort>(DEFAULT_SORT);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setProposal(await getPetClusters(identity, species, sort));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recommendations");
    } finally {
      setLoading(false);
    }
  }, [identity, species, sort]);

  useEffect(() => {
    setNotice(null);
    load();
  }, [load]);

  const approve = useCallback(
    async (classificationIds: number[]) => {
      // The ids the owner left selected, passed explicitly. The server never
      // re-derives cluster membership (issue #142), so a stale cluster on the
      // client cannot approve a photo that was deselected here.
      const result = await approveCluster(identity, species, classificationIds);

      // Report the shortfall rather than swallowing it: an approval of N
      // that applied fewer than N has to say so, and why.
      const skipped = result.skips
        .map((skip) => skip.reason)
        .filter((reason, index, reasons) => reasons.indexOf(reason) === index)
        .join(", ");

      setNotice(
        result.skipped === 0
          ? `Tagged ${result.applied} ${result.applied === 1 ? "photo" : "photos"} as ${identity}.`
          : `Tagged ${result.applied} of ${result.applied + result.skipped} photos as ${identity}. Skipped ${result.skipped}: ${skipped}.`,
      );

      onApproved?.(result.applied);

      await load();
    },
    [identity, species, onApproved, load],
  );

  const reject = useCallback(
    async (classificationIds: number[]) => {
      const result = await rejectCluster(identity, species, classificationIds);

      const skipped = result.skips
        .map((skip) => skip.reason)
        .filter((reason, index, reasons) => reasons.indexOf(reason) === index)
        .join(", ");

      // Says what it did and what it did not, the same way an approval does.
      // "Still pending" is the important half: a rejection removes a wrong
      // recommendation without deciding anything, so these photos have not
      // gone away, they have gone back to waiting for an identity.
      setNotice(
        result.skipped === 0
          ? `Marked ${result.applied} ${result.applied === 1 ? "photo" : "photos"} as not ${identity}. They stay pending until an identity is chosen.`
          : `Marked ${result.applied} of ${result.applied + result.skipped} photos as not ${identity}. Skipped ${result.skipped}: ${skipped}.`,
      );

      await load();
    },
    [identity, species, load],
  );

  return (
    <section className="space-y-4" aria-label={`Recommendations for ${identity}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Recommendations for {identity}
        </h2>

        {proposal && proposal.clusters.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {proposal.clustered_count} pending{" "}
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
          {SORT_OPTIONS.map((option) => (
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
        <p className="text-sm text-muted-foreground">Grouping recommendations…</p>
      )}

      {!error && !loading && proposal && proposal.clusters.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No pending recommendations for {identity}. Photos appear here once
          classification proposes {identity} for a crop nobody has reviewed yet.
        </p>
      )}

      {!error && !loading && proposal && proposal.clusters.length > 0 && (
        <div className="space-y-4">
          {proposal.clusters.map((cluster) => (
            <ClusterCard
              // Keyed by pet as well as cluster. The re-fetch on a pet change
              // already unmounts these while it loads, but that is incidental
              // -- this makes "a selection never outlives its pet" a property
              // of the tree rather than of the loading state.
              key={`${identity}-${cluster.id}`}
              cluster={cluster}
              identity={identity}
              onApprove={approve}
              onReject={reject}
            />
          ))}
        </div>
      )}

      {!error && !loading && proposal && proposal.excluded.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {proposal.excluded.length}{" "}
          {proposal.excluded.length === 1 ? "photo has" : "photos have"} no stored
          embedding and could not be grouped — review{" "}
          {proposal.excluded.length === 1 ? "it" : "them"} individually.
        </p>
      )}

      {!error && !loading && proposal?.truncated && (
        <p className="text-sm text-muted-foreground">
          Showing the strongest {proposal.candidate_count} recommendations; more
          appear once these are settled.
        </p>
      )}
    </section>
  );
}
