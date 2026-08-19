import { useCallback, useEffect, useState } from "react";

import { IconRefresh } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { approveCluster, getPetClusters } from "@/lib/api";
import type { ClusterProposal, RecommendationCluster } from "@/types/clusters";
import { ClusterCard } from "./ClusterCard";

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

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      setProposal(await getPetClusters(identity, species));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recommendations");
    } finally {
      setLoading(false);
    }
  }, [identity, species]);

  useEffect(() => {
    setNotice(null);
    load();
  }, [load]);

  const approve = useCallback(
    async (cluster: RecommendationCluster) => {
      const result = await approveCluster(
        identity,
        species,
        cluster.members.map((member) => member.classification_id),
      );

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
              key={cluster.id}
              cluster={cluster}
              identity={identity}
              onApprove={approve}
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
