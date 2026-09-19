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
    PendingPool,
    RecommendationCluster,
    RecommendationClusterService,
)
from immich_dog_tagger.services.review_query import (
    SPATIAL_MISMATCH_THRESHOLD,
    TEMPORAL_MISMATCH_THRESHOLD,
    ReviewQueryService,
)

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
class GroupMismatch:
    """A cluster member whose own top-ranked, weighted-by-time-and-location
    prediction (`candidates[0]`, already sorted by weighted_score -- see
    classifier.py) is not this group's identity: it was pooled into the
    cluster because the identity appears *somewhere* in its candidates and
    it looked visually similar, not because the identity is actually its
    best match once capture time/location are weighed in. See
    docs/specs/review-groups-temporal-spatial-refinement.md.

    `reason` reuses the same vocabulary Queue mode's `_review_reason()`
    already shows for `temporal-mismatch`/`location-mismatch`, plus
    `different-top-prediction` when neither weight alone explains the
    mismatch."""

    classification_id: int
    reason: str


@dataclass(frozen=True)
class ReviewGroup:
    """One identity's cluster, carrying the identity/species it belongs to
    so the caller can act on it (approve/reject) without having to infer
    which pet a group is for."""

    identity: str
    species: Species
    cluster: RecommendationCluster
    # Members flagged by the temporal/spatial refinement pass, empty when
    # every member's own top-ranked prediction agrees with `identity`.
    mismatches: list[GroupMismatch]


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


def _mismatch_reason(
    group_identity: str,
    row: tuple[str | None, list[dict]],
) -> str | None:
    """
    None when `group_identity` is this member's own top-ranked, weighted
    prediction -- `candidates[0]` when candidates exist (already sorted by
    weighted_score = similarity * temporal_weight * spatial_weight, see
    classifier.py), falling back to the accepted identity on the rare row
    with no stored candidates at all. Otherwise the same reason vocabulary
    Queue mode's `_review_reason()` already shows, read off
    `group_identity`'s own candidate entry (not necessarily the top one)
    rather than re-deriving anything: `temporal-mismatch` or
    `location-mismatch` when that entry's own weight explains why it lost
    the ranking, `different-top-prediction` when neither does (e.g. it
    simply lost on raw visual similarity).
    """
    accepted, candidates = row
    candidates = candidates or []
    top_identity = candidates[0].get("identity") if candidates else accepted

    if top_identity == group_identity:
        return None

    own = next(
        (
            candidate
            for candidate in candidates
            if candidate.get("identity") == group_identity
        ),
        None,
    )

    if own is not None:
        if own.get("temporal_weight", 1.0) < TEMPORAL_MISMATCH_THRESHOLD:
            return "temporal-mismatch"

        if own.get("spatial_weight", 1.0) < SPATIAL_MISMATCH_THRESHOLD:
            return "location-mismatch"

    return "different-top-prediction"


def _cluster_mismatches(
    identity: str,
    cluster: RecommendationCluster,
    rows_by_id: dict[int, tuple[str | None, list[dict]]],
) -> list[GroupMismatch]:
    mismatches = []

    for member in cluster.members:
        row = rows_by_id.get(member.classification_id)

        # Fails open (no flag) rather than raising: every cluster member
        # came from this same species' pool, so this should always hit,
        # but a refinement pass is not the place to turn a lookup gap into
        # a 500 for the whole group list.
        if row is None:
            continue

        reason = _mismatch_reason(identity, row)

        if reason is not None:
            mismatches.append(
                GroupMismatch(classification_id=member.classification_id, reason=reason)
            )

    return mismatches


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
        # Every pair for the same species shares one candidate pool
        # (issue #334): fetched once per species here and sliced per
        # identity by `clusters_in_pool()`, instead of each identity
        # re-running the same full-species scan `clusters()` itself would
        # do. Safe because this loop, like `clusters()`, never writes
        # between identities -- see `clusters_in_pool()`'s docstring.
        pools: dict[Species, PendingPool] = {}
        # Same pool, reshaped once per species into classification_id ->
        # (accepted identity, candidates) so the refinement pass below can
        # look up a member's own weighted-ranked prediction without a
        # second query per identity.
        rows_by_species: dict[Species, dict[int, tuple[str | None, list[dict]]]] = {}

        for identity, species in pairs:
            if species not in pools:
                pool = self.cluster_service.pending_pool(species)
                pools[species] = pool
                rows_by_species[species] = {
                    row.id: (row.identity, row.candidates) for row in pool.rows
                }

            proposal = self.cluster_service.clusters_in_pool(
                identity=identity, species=species, pool=pools[species], sort=sort
            )
            rows_by_id = rows_by_species[species]

            groups.extend(
                ReviewGroup(
                    identity=identity,
                    species=species,
                    cluster=cluster,
                    mismatches=_cluster_mismatches(identity, cluster, rows_by_id),
                )
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
