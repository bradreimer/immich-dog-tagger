"""
Group the *entire active review queue* into visually-similar batches a
reviewer can settle in one action from the Review tab (issue TBD, see
docs/specs/review-tab-batch-approval.md).

This is deliberately a thin wrapper around the existing, tested
`RecommendationClusterService`: v1.8 already solved "cluster one identity's
pending candidates" and `ClusterApprovalService` already solved "approve/
reject a selection from one cluster as N ordinary corrections". Neither is
touched here. The only new behavior is picking *which* identities to cluster
-- every identity with at least one pending review-queue item, rather than
one identity the caller selects up front -- and merging their clusters into
one list.

A read, like `RecommendationClusterService.clusters()`: it writes nothing.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClusterSort, Species
from immich_dog_tagger.models import Crop, CropClassification, ReviewAction
from immich_dog_tagger.services.clusters import (
    DEFAULT_CLUSTER_SORT,
    MAX_CANDIDATE_POOL,
    RecommendationCluster,
    RecommendationClusterService,
)
from immich_dog_tagger.services.review_query import ReviewQueryService

logger = logging.getLogger(__name__)

# A cluster of one photo has no batching benefit over correcting it from the
# ordinary Queue mode -- it would just be the same single decision, wrapped
# in group chrome. Grouped mode only shows clusters that actually save the
# reviewer some number of decisions.
MIN_GROUP_SIZE = 2

# How many distinct (identity, species) pairs a single request will cluster.
# Clustering itself is already bounded per identity (MAX_CANDIDATE_POOL), so
# this bounds the *other* axis -- a library with an unusually large number of
# identities all carrying pending work -- so one request can't fan out into
# an unbounded number of clustering passes. A request that hits this cap
# reports it rather than silently dropping identities past the cut.
MAX_GROUP_IDENTITIES = 100


@dataclass(frozen=True)
class ReviewGroup:
    """One identity's cluster, carrying the identity/species it belongs to
    so the caller can act on it (approve/reject) without having to infer
    which pet a group is for."""

    identity: str
    species: Species
    cluster: RecommendationCluster


@dataclass(frozen=True)
class ReviewGroupsProposal:
    # Largest group first (issue TBD): the biggest throughput win surfaces
    # first, the same "surest/biggest first" instinct FR-5's confidence sort
    # already applies within a single pet's clusters.
    groups: list[ReviewGroup]
    # How many distinct identities were clustered to build this list.
    identity_count: int
    # True when more identities had pending work than MAX_GROUP_IDENTITIES
    # and the scan was capped.
    truncated_identities: bool
    sort: ClusterSort


class ReviewGroupingService:
    """
    Builds `ReviewGroup`s across the whole active review queue, not one
    identity at a time. Read-only by construction, same contract as
    `RecommendationClusterService`.
    """

    def __init__(
        self,
        session: Session,
        *,
        max_pool: int = MAX_CANDIDATE_POOL,
        max_identities: int = MAX_GROUP_IDENTITIES,
    ):
        self.session = session
        self.max_identities = max_identities
        self.review_query = ReviewQueryService(session)
        self.cluster_service = RecommendationClusterService(
            session,
            max_pool=max_pool,
        )

    def groups(
        self,
        *,
        sort: ClusterSort = DEFAULT_CLUSTER_SORT,
    ) -> ReviewGroupsProposal:
        pairs = self._pending_identity_species_pairs()

        truncated_identities = len(pairs) > self.max_identities

        if truncated_identities:
            logger.info(
                "Review grouping capped at %d of %d identities with pending work",
                self.max_identities,
                len(pairs),
            )

        pairs = pairs[: self.max_identities]

        groups: list[ReviewGroup] = []

        for identity, species in pairs:
            proposal = self.cluster_service.clusters(
                identity=identity, species=species, sort=sort
            )

            groups.extend(
                ReviewGroup(identity=identity, species=species, cluster=cluster)
                for cluster in proposal.clusters
                if cluster.size >= MIN_GROUP_SIZE
            )

        groups.sort(key=lambda group: group.cluster.size, reverse=True)

        return ReviewGroupsProposal(
            groups=groups,
            identity_count=len(pairs),
            truncated_identities=truncated_identities,
            sort=sort,
        )

    def _pending_identity_species_pairs(self) -> list[tuple[str, Species]]:
        """
        Every (identity, species) pair the classifier put forward -- as the
        accepted identity or a stored candidate -- for at least one active
        review-queue item (no review action yet). Mirrors
        `RecommendationClusterService._candidate_ids()`'s pool membership
        rule, just scanning every identity at once instead of testing one.

        A single query, since SQLite has no portable "JSON array contains"
        predicate: candidate matching happens in Python the same way
        `_candidate_ids()` already does it, over the pending pool only (not
        the whole library), which is what keeps this bounded.
        """
        rows = self.session.execute(
            select(
                CropClassification.identity,
                CropClassification.candidates,
                Crop.species,
            )
            .join(Crop, Crop.id == CropClassification.crop_id)
            .where(
                ~exists(
                    select(ReviewAction.id).where(
                        ReviewAction.classification_id == CropClassification.id,
                    )
                )
            )
            .where(
                (CropClassification.identity.is_not(None))
                | (CropClassification.candidates != [])
            )
        ).all()

        pairs: set[tuple[str, Species]] = set()

        for row in rows:
            if row.identity:
                pairs.add((row.identity, row.species))

            for candidate in row.candidates or []:
                candidate_identity = candidate.get("identity")

                if candidate_identity:
                    pairs.add((candidate_identity, row.species))

        # Sorted for a deterministic, stable truncation order -- two
        # requests against the same data cap the same identities out.
        return sorted(pairs, key=lambda pair: (pair[1].value, pair[0]))
