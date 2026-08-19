"""
Cluster a pet's pending recommendations, and approve a selection from one
cluster in one action (issues #141 and #142).

Two services live here, deliberately on opposite sides of the read/write
line:

- `RecommendationClusterService` is a **read**. It groups the crops the
  classifier already proposed for one pet and writes nothing -- no
  prediction, no confidence, no identity. Running it twice with no
  approvals in between changes no rows.
- `ClusterApprovalService` is the **write**, and it is nothing new: every
  member goes through `ClassificationCorrectionService.correct()`, so an
  approval of N members is N ordinary corrections with ordinary
  `ReviewAction` and `EmbeddingExample` provenance. Album membership
  reconciles on the next operator-triggered sync (ADR-006), not here.

Both are bounded. Clustering pools at most `MAX_CANDIDATE_POOL`
candidates, and an approval commits every `APPROVAL_BATCH_SIZE` members so
a failure partway through leaves committed progress rather than a
rolled-back hour (the DetectionService/ClassificationService pattern).
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from immich_dog_tagger.clustering import (
    DEFAULT_CLUSTER_DISTANCE,
    agglomerative_clusters,
    medoid,
)
from immich_dog_tagger.embeddings import blob_to_embedding
from immich_dog_tagger.enums import Species
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.review_query import (
    REVIEW_ITEM_RELATIONSHIPS,
    ReviewItem,
    ReviewQueryService,
)

logger = logging.getLogger(__name__)

# A pet with thousands of pending candidates must not produce an unbounded
# clustering pass: the distance matrix is O(n^2) and the merge loop scans
# it once per merge. 500 keeps a pass comfortably interactive (see
# tests/test_scale.py, which pins the shape of that cost) while covering
# far more candidates than one sitting of approvals will get through.
MAX_CANDIDATE_POOL = 500

# Members are corrected one at a time and committed in batches, so an
# approval that fails partway leaves the members already applied committed
# instead of rolling all of them back. Small enough that state.db's single
# write lock is released regularly (issues #104/#107).
APPROVAL_BATCH_SIZE = 25

# An approval is an interactive, synchronous write (ADR-006): it stays in
# the request rather than becoming a job, so its size has to be bounded.
MAX_APPROVAL_SIZE = 1000


def proposes_identity(
    identity: str,
    *,
    accepted: str | None,
    candidates: list[dict] | None,
) -> bool:
    """
    Whether the classifier put `identity` forward for this crop at all --
    as the accepted identity, or as one of the stored runner-up candidates.

    This is the membership rule for a pet's candidate pool, shared by the
    read that builds the clusters and the write that approves a selection
    from one, so the write validates against the same rule the read
    promised.
    """
    if accepted == identity:
        return True

    return any(
        candidate.get("identity") == identity for candidate in (candidates or [])
    )


@dataclass(frozen=True)
class ExcludedCandidate:
    """A pooled candidate that could not be clustered, and why."""

    classification_id: int
    crop_id: int
    reason: str


@dataclass(frozen=True)
class RecommendationCluster:
    # Derived from the members (their lowest classification id), so the
    # same pool always yields the same cluster ids.
    id: int
    representative: ReviewItem
    members: list[ReviewItem]
    min_similarity: float
    max_similarity: float
    earliest_captured_at: datetime | None
    latest_captured_at: datetime | None

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(frozen=True)
class ClusterProposal:
    identity: str
    species: Species
    clusters: list[RecommendationCluster]
    excluded: list[ExcludedCandidate]
    # Everything pooled for this pet, including the excluded candidates.
    candidate_count: int
    distance_threshold: float
    # True when the pet had more pending candidates than MAX_CANDIDATE_POOL
    # and the pool was capped -- the owner sees the strongest ones first and
    # the rest appear once these are approved.
    truncated: bool

    @property
    def clustered_count(self) -> int:
        return sum(cluster.size for cluster in self.clusters)


@dataclass(frozen=True)
class ApprovalSkip:
    classification_id: int
    reason: str


@dataclass(frozen=True)
class ApprovalSummary:
    identity: str
    applied: int
    skips: list[ApprovalSkip]

    @property
    def skipped(self) -> int:
        return len(self.skips)


class RecommendationClusterService:
    """
    Groups one pet's pending recommendations into clusters of visually
    similar crops. Read-only by construction: it opens no transaction of
    its own and mutates nothing it loads.
    """

    def __init__(
        self,
        session: Session,
        *,
        distance_threshold: float = DEFAULT_CLUSTER_DISTANCE,
        max_pool: int = MAX_CANDIDATE_POOL,
    ):
        self.session = session
        self.distance_threshold = distance_threshold
        self.max_pool = max_pool
        self.review_query = ReviewQueryService(session)

    def clusters(
        self,
        *,
        identity: str,
        species: Species,
    ) -> ClusterProposal:
        """
        Cluster the unreviewed crops of `species` the classifier proposed
        for `identity` -- either as the accepted identity or as one of the
        stored candidates.
        """
        self._require_identity(identity, species)

        classification_ids, truncated = self._candidate_ids(identity, species)

        classifications = self._load(classification_ids)

        embeddings: list[np.ndarray] = []
        clusterable: list[CropClassification] = []
        excluded: list[ExcludedCandidate] = []

        for classification in classifications:
            if classification.embedding is None:
                # Nothing to measure similarity with. Reported rather than
                # dropped silently, and rather than crashing the pass.
                excluded.append(
                    ExcludedCandidate(
                        classification_id=classification.id,
                        crop_id=classification.crop_id,
                        reason="no-embedding",
                    )
                )
                continue

            embeddings.append(blob_to_embedding(classification.embedding))
            clusterable.append(classification)

        clusters = self._build_clusters(clusterable, embeddings, identity)

        return ClusterProposal(
            identity=identity,
            species=species,
            clusters=clusters,
            excluded=excluded,
            candidate_count=len(classifications),
            distance_threshold=self.distance_threshold,
            truncated=truncated,
        )

    def _build_clusters(
        self,
        classifications: list[CropClassification],
        embeddings: list[np.ndarray],
        identity: str,
    ) -> list[RecommendationCluster]:
        if not classifications:
            return []

        matrix = np.vstack(embeddings)

        groups = agglomerative_clusters(
            matrix,
            distance_threshold=self.distance_threshold,
        )

        clusters = [
            self._to_cluster(
                [classifications[index] for index in group],
                classifications[medoid(matrix, group)],
                identity,
            )
            for group in groups
        ]

        # agglomerative_clusters() already orders by size then by member
        # index, and the pool it saw was ordered deterministically -- this
        # re-sort only makes the tie-break explicit in terms the API
        # exposes (cluster id), rather than positional indices.
        return sorted(clusters, key=lambda cluster: (-cluster.size, cluster.id))

    def _to_cluster(
        self,
        members: list[CropClassification],
        representative: CropClassification,
        identity: str,
    ) -> RecommendationCluster:
        ordered = sorted(members, key=lambda classification: classification.id)

        items = [self.review_query.review_item(member) for member in ordered]

        similarities = [self._similarity_for(member, identity) for member in ordered]

        captured = [item.captured_at for item in items if item.captured_at is not None]

        return RecommendationCluster(
            id=ordered[0].id,
            representative=self.review_query.review_item(representative),
            members=items,
            min_similarity=min(similarities),
            max_similarity=max(similarities),
            earliest_captured_at=min(captured, default=None),
            latest_captured_at=max(captured, default=None),
        )

    def _similarity_for(
        self,
        classification: CropClassification,
        identity: str,
    ) -> float:
        """
        How similar this crop is *to the pet being clustered*. For a crop
        the classifier already attributes to the pet that is the stored
        confidence; for one where the pet is only a runner-up candidate it
        is that candidate's own similarity, never the top candidate's --
        reporting the latter would overstate the case for this pet.
        """
        if classification.identity == identity:
            return classification.confidence

        for candidate in classification.candidates:
            if candidate.get("identity") == identity:
                return float(candidate.get("similarity", 0.0))

        return 0.0

    def _require_identity(self, identity: str, species: Species) -> Identity:
        pet = self.session.scalar(
            select(Identity).where(
                Identity.name == identity,
                Identity.species == species,
            )
        )

        if pet is None:
            raise ValueError(f"No {species.value} named {identity!r}")

        return pet

    def _candidate_ids(
        self,
        identity: str,
        species: Species,
    ) -> tuple[list[int], bool]:
        """
        The candidate pool: unreviewed classifications of crops of this
        species where the pet is either the accepted identity or one of the
        stored candidates.

        Done in two steps on purpose. The first query reads only scalar
        columns, so the JSON candidate list can be matched in Python (SQLite
        has no portable "JSON array contains" predicate) without dragging
        the crop/detection/asset chain along; the second loads only the
        capped pool, with the eager-loading `_load()` relies on.
        """
        rows = self.session.execute(
            select(
                CropClassification.id,
                CropClassification.identity,
                CropClassification.candidates,
                CropClassification.confidence,
            )
            .where(CropClassification.crop.has(Crop.species == species))
            .where(
                ~exists(
                    select(ReviewAction.id).where(
                        ReviewAction.classification_id == CropClassification.id,
                    )
                )
            )
            .where(
                (CropClassification.identity == identity)
                | (CropClassification.candidates != [])
            )
            # Strongest case for this pet first, so a capped pool keeps the
            # candidates most worth approving. The id tie-break makes the
            # ordering total, which is what keeps clustering deterministic.
            .order_by(
                CropClassification.confidence.desc(),
                CropClassification.id.asc(),
            )
        ).all()

        matched = [
            row.id
            for row in rows
            if proposes_identity(
                identity,
                accepted=row.identity,
                candidates=row.candidates,
            )
        ]

        truncated = len(matched) > self.max_pool

        if truncated:
            logger.info(
                "Cluster pool for %r capped at %d of %d pending candidates",
                identity,
                self.max_pool,
                len(matched),
            )

        return matched[: self.max_pool], truncated

    def _load(self, classification_ids: list[int]) -> list[CropClassification]:
        if not classification_ids:
            return []

        classifications = self.session.scalars(
            select(CropClassification)
            .options(*REVIEW_ITEM_RELATIONSHIPS)
            .where(CropClassification.id.in_(classification_ids))
            .order_by(CropClassification.id.asc())
        ).all()

        return list(classifications)


class ClusterApprovalService:
    """
    Applies a pet's identity to an explicitly listed set of members, as N
    ordinary corrections.
    """

    def __init__(
        self,
        session: Session,
        correction_service: ClassificationCorrectionService,
        *,
        batch_size: int = APPROVAL_BATCH_SIZE,
        max_approval_size: int = MAX_APPROVAL_SIZE,
    ):
        self.session = session
        self.correction_service = correction_service
        self.batch_size = batch_size
        self.max_approval_size = max_approval_size

    def approve(
        self,
        *,
        identity: str,
        species: Species,
        classification_ids: list[int],
    ) -> ApprovalSummary:
        """
        Assign `identity` to each of `classification_ids`.

        The caller submits an explicit list -- the owner's selection (issue
        #142) -- and this never re-derives "the cluster" from it. Approving
        membership computed here would sweep back in exactly the photos the
        owner deselected, and would do it from a cluster the client may no
        longer be looking at.

        Every id is checked against the pool it claims to come from, so an
        id outside this pet's recommendations is refused rather than
        silently labelled. Every member that cannot be assigned is reported
        with a reason rather than dropped: a silent shortfall between
        "approve 40 photos" and 31 assignments is the bug DT-1117's
        accounting convention exists to prevent.
        """
        if not classification_ids:
            # Deselecting every member is a deliberate "approve nothing", not
            # an approval of the whole cluster. Refused so it can never be
            # read as the latter.
            raise ValueError("Cannot approve an empty selection")

        if len(classification_ids) > self.max_approval_size:
            raise ValueError(
                f"Cannot approve more than {self.max_approval_size} photos at once"
            )

        pet = self.session.scalar(
            select(Identity).where(
                Identity.name == identity,
                Identity.species == species,
            )
        )

        if pet is None:
            raise ValueError(f"No {species.value} named {identity!r}")

        applied = 0
        skips: list[ApprovalSkip] = []
        seen: set[int] = set()
        since_commit = 0

        try:
            for classification_id in classification_ids:
                if classification_id in seen:
                    skips.append(ApprovalSkip(classification_id, "duplicate"))
                    continue

                seen.add(classification_id)

                reason = self._rejection_reason(
                    classification_id,
                    identity,
                    species,
                )

                if reason is not None:
                    skips.append(ApprovalSkip(classification_id, reason))
                    continue

                self.correction_service.correct(
                    classification_id,
                    identity,
                    commit=False,
                )

                applied += 1
                since_commit += 1

                if since_commit >= self.batch_size:
                    self.session.commit()
                    since_commit = 0

            if since_commit:
                self.session.commit()
        except Exception:
            # Discard only the batch still in flight; everything committed
            # by an earlier checkpoint stays applied.
            self.session.rollback()
            raise

        logger.info(
            "Cluster approval for %r: %d applied, %d skipped",
            identity,
            applied,
            len(skips),
        )

        return ApprovalSummary(
            identity=identity,
            applied=applied,
            skips=skips,
        )

    def _rejection_reason(
        self,
        classification_id: int,
        identity: str,
        species: Species,
    ) -> str | None:
        classification = self.session.get(CropClassification, classification_id)

        if classification is None:
            return "not-found"

        if classification.review_actions:
            # A human already settled this one; a bulk approval must not
            # overwrite an individual decision made from the Review page.
            return "already-reviewed"

        if classification.crop.species != species:
            return "species-mismatch"

        if not proposes_identity(
            identity,
            accepted=classification.identity,
            candidates=classification.candidates,
        ):
            # The approval names a crop the classifier never put this pet
            # forward for, so it was never in the cluster the owner was
            # looking at. Refused rather than applied: a client bug, a stale
            # page, or a hand-written request must not be able to write a
            # label the owner never saw proposed.
            return "not-recommended"

        return None
