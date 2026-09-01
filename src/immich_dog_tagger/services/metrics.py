"""
Learning-progress metrics.

Answers the question v1.0.0 exists to answer: is manual review becoming
less necessary? Every count states its own denominator/scope explicitly
(see LearningMetrics fields) rather than presenting a bare percentage.
Precision/accuracy are intentionally not computed here -- they would
require a held-out evaluation set distinct from the reviews used as
ground truth, which does not exist in v1.0.0.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus, Species
from immich_dog_tagger.models import (
    Asset,
    ClassificationPass,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.policy import DEFAULT_POLICY, ClassifierPolicy
from immich_dog_tagger.services.review_query import ReviewQueryService

# Detection has run to completion for an asset in one of these states.
# The current pipeline only ever writes DETECTED (detect.py is the last
# stage that touches Asset.status), but databases carrying older rows can
# hold the later states, and CLASSIFICATION_FAILED still means detection
# itself finished -- so all four count as "detection has had its chance".
DETECTION_COMPLETE_STATUSES = frozenset(
    {
        AssetStatus.DETECTED,
        AssetStatus.CLASSIFIED,
        AssetStatus.TAGGED,
        AssetStatus.CLASSIFICATION_FAILED,
    }
)

# Still queued for the pipeline: detection has not had its chance yet.
DETECTION_PENDING_STATUSES = frozenset(
    {
        AssetStatus.PENDING,
        AssetStatus.DOWNLOADED,
    }
)

# Cannot reach detection without operator action.
DETECTION_BLOCKED_STATUSES = frozenset(
    {
        AssetStatus.DOWNLOAD_FAILED,
        AssetStatus.DETECTION_FAILED,
        AssetStatus.UNSUPPORTED,
    }
)


@dataclass(frozen=True)
class ClassificationPassSummary:
    id: int
    status: str
    classifier_version: str
    threshold: float
    eligible_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    changed_count: int
    labeled_example_count: int | None
    review_queue_size: int | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_pass(
        cls, classification_pass: ClassificationPass
    ) -> ClassificationPassSummary:
        return cls(
            id=classification_pass.id,
            status=classification_pass.status.value,
            classifier_version=classification_pass.classifier_version,
            threshold=classification_pass.threshold,
            eligible_count=classification_pass.eligible_count,
            confident_count=classification_pass.confident_count,
            needs_review_count=classification_pass.needs_review_count,
            unknown_count=classification_pass.unknown_count,
            changed_count=classification_pass.changed_count,
            labeled_example_count=classification_pass.labeled_example_count,
            review_queue_size=classification_pass.review_queue_size,
            error_message=classification_pass.error_message,
            started_at=classification_pass.started_at,
            completed_at=classification_pass.completed_at,
        )


@dataclass(frozen=True)
class SpeciesMetrics:
    """
    The same core counts as LearningMetrics, scoped to one species (DT-1110)
    -- so "how much manual review is left" is never silently averaged across
    dogs and cats into one misleading number, even though the review queue
    itself stays unified.
    """

    species: str
    eligible_count: int
    confident_count: int
    unknown_count: int
    reviewed_count: int
    labeled_example_count: int
    coverage: float | None


@dataclass(frozen=True)
class DetectionCoverage:
    """
    Coverage of the *library* rather than of the crops detection happened
    to produce (issue #146).

    Every other figure on this page has a CropClassification denominator,
    so none of them can see a photo YOLO never detected anything in. These
    counts have a photo denominator instead, which is the only way the
    owner can tell "my library is tagged" from "detection quietly skipped
    a lot of it".

    Explicitly *not* accuracy or recall: nothing here is compared against
    labeled ground truth, and the overwhelming majority of photos with no
    crop legitimately contain no pet. `with_crops_rate` answers exactly
    one question -- of the photos detection has finished with, what share
    produced at least one pet crop -- and `without_crops_count` names the
    population a missed pet would be hiding in.
    """

    # Every asset row the scanner knows about, whatever stage it reached.
    scanned_count: int
    # The stated denominator: photos detection has finished with.
    processed_count: int
    with_crops_count: int
    without_crops_count: int
    # Scanned but not yet through detection -- not evidence of anything
    # missed, just work the pipeline still has queued.
    awaiting_detection_count: int
    # Cannot reach detection without operator action (failed download or
    # detection, unsupported file type).
    unprocessable_count: int
    with_crops_rate: float | None


@dataclass(frozen=True)
class LearningMetrics:
    eligible_count: int
    reviewed_count: int
    labeled_example_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    coverage: float | None
    review_rate: float | None
    unknown_rate: float | None
    review_queue_size: int
    no_review_needed_count: int
    automation_rate: float | None
    last_reclassification: ClassificationPassSummary | None
    pass_history: list[ClassificationPassSummary]
    by_species: list[SpeciesMetrics]
    detection_coverage: DetectionCoverage


class MetricsService:
    def __init__(
        self,
        session: Session,
        policy: ClassifierPolicy = DEFAULT_POLICY,
        # One ClassificationPass row per Reclassify run -- effectively full
        # history for any realistic cadence (even daily runs take ~1.5
        # years to reach this), while still bounding the query rather than
        # leaving it truly unbounded. The UI downsamples for display; this
        # limit is a resource bound, not a display window.
        history_limit: int = 500,
    ):
        self.session = session
        self.policy = policy
        self.history_limit = history_limit
        self.review_query = ReviewQueryService(session, policy=policy)

    def learning_metrics(self) -> LearningMetrics:
        eligible_count = self._count(
            select(func.count()).select_from(CropClassification)
        )

        reviewed_count = self.review_query.review_queue_stats().reviewed

        labeled_example_count = self._count(
            select(func.count()).select_from(EmbeddingExample)
        )

        unknown_count = self._count(
            select(func.count())
            .select_from(CropClassification)
            .where(CropClassification.identity.is_(None))
        )

        confident_count = self._count(
            select(func.count())
            .select_from(CropClassification)
            .where(
                CropClassification.identity.is_not(None),
                CropClassification.confidence >= self.policy.confident_threshold,
            )
        )

        needs_review_count = eligible_count - unknown_count - confident_count

        # The actual pending-work queue -- unreviewed items that are
        # unknown or below the confident threshold -- as opposed to
        # needs_review_count above, which (given the classifier never
        # assigns an identity below its own threshold) is populated almost
        # entirely by legacy/manual data rather than organic AUTO output.
        review_queue_size = self.review_query.review_queue_count()

        # "No review needed" is the complement of the queue: it answers
        # "how many images can I ignore right now," which includes both
        # confidently auto-classified items AND anything a human has
        # already reviewed (regardless of that item's confidence) -- not
        # only "how many did the classifier get right without help."
        no_review_needed_count = eligible_count - review_queue_size

        # SQLite's CURRENT_TIMESTAMP has only second-level resolution, so
        # started_at alone cannot break ties between passes created within
        # the same second -- id is a reliable secondary sort key since pass
        # ids are assigned in creation order.
        recent_passes = self.session.scalars(
            select(ClassificationPass)
            .order_by(
                ClassificationPass.started_at.desc(),
                ClassificationPass.id.desc(),
            )
            .limit(self.history_limit)
        ).all()

        pass_summaries = [
            ClassificationPassSummary.from_pass(classification_pass)
            for classification_pass in reversed(recent_passes)
        ]

        return LearningMetrics(
            eligible_count=eligible_count,
            reviewed_count=reviewed_count,
            labeled_example_count=labeled_example_count,
            confident_count=confident_count,
            needs_review_count=needs_review_count,
            unknown_count=unknown_count,
            coverage=(confident_count / eligible_count) if eligible_count else None,
            review_rate=(reviewed_count / eligible_count) if eligible_count else None,
            unknown_rate=(unknown_count / eligible_count) if eligible_count else None,
            review_queue_size=review_queue_size,
            no_review_needed_count=no_review_needed_count,
            automation_rate=(no_review_needed_count / eligible_count)
            if eligible_count
            else None,
            last_reclassification=pass_summaries[-1] if pass_summaries else None,
            pass_history=pass_summaries,
            by_species=self._species_breakdown(),
            detection_coverage=self._detection_coverage(),
        )

    def _detection_coverage(self) -> DetectionCoverage:
        """
        Two fixed aggregate queries regardless of library size -- a
        grouped count over asset status, and one distinct-asset count over
        crops. No per-asset query and no row-by-row Python loop, so this
        stays as cheap at 30,000 photos as at 30.

        The denominator is deliberately "photos detection has finished
        with" rather than every scanned photo: assets still queued for
        download/detection have not had their chance yet, and counting
        them as uncovered would make the figure move with pipeline
        backlog instead of with detection outcome.
        """
        status_counts = {
            status: count
            for status, count in self.session.execute(
                select(Asset.status, func.count()).group_by(Asset.status)
            ).all()
        }

        def total(statuses) -> int:
            return sum(status_counts.get(status, 0) for status in statuses)

        scanned_count = sum(status_counts.values())
        processed_count = total(DETECTION_COMPLETE_STATUSES)

        # Scoped to the same status set as the denominator so the two can
        # never disagree -- an asset rescanned back to PENDING keeps its
        # old crops, and counting those here would let with_crops_count
        # exceed processed_count.
        with_crops_count = self._count(
            select(func.count(func.distinct(Detection.asset_id)))
            .select_from(Crop)
            .join(Detection, Crop.detection_id == Detection.id)
            .join(Asset, Detection.asset_id == Asset.id)
            .where(Asset.status.in_(DETECTION_COMPLETE_STATUSES))
        )

        return DetectionCoverage(
            scanned_count=scanned_count,
            processed_count=processed_count,
            with_crops_count=with_crops_count,
            without_crops_count=processed_count - with_crops_count,
            awaiting_detection_count=total(DETECTION_PENDING_STATUSES),
            unprocessable_count=total(DETECTION_BLOCKED_STATUSES),
            with_crops_rate=(with_crops_count / processed_count)
            if processed_count
            else None,
        )

    def _species_breakdown(self) -> list[SpeciesMetrics]:
        """
        Grouped queries, not one query per species -- stays cheap regardless
        of how many crops/examples exist, matching this file's existing
        "explicit denominators, no per-row Python loop" style.

        Keyed off `Crop.species` -- the corrected, authoritative value a
        reviewer may have overridden via species correction -- not
        `Detection.label` (the detector's original, possibly-wrong raw
        output). The two always matched before species correction existed,
        so this only changes behavior for crops whose species a reviewer
        has since corrected.
        """
        eligible_by_species = dict(
            self.session.execute(
                select(Crop.species, func.count())
                .select_from(CropClassification)
                .join(Crop, CropClassification.crop_id == Crop.id)
                .group_by(Crop.species)
            ).all()
        )

        confident_by_species = dict(
            self.session.execute(
                select(Crop.species, func.count())
                .select_from(CropClassification)
                .join(Crop, CropClassification.crop_id == Crop.id)
                .where(
                    CropClassification.identity.is_not(None),
                    CropClassification.confidence >= self.policy.confident_threshold,
                )
                .group_by(Crop.species)
            ).all()
        )

        unknown_by_species = dict(
            self.session.execute(
                select(Crop.species, func.count())
                .select_from(CropClassification)
                .join(Crop, CropClassification.crop_id == Crop.id)
                .where(CropClassification.identity.is_(None))
                .group_by(Crop.species)
            ).all()
        )

        reviewed_by_species = dict(
            self.session.execute(
                select(Crop.species, func.count(func.distinct(CropClassification.id)))
                .select_from(CropClassification)
                .join(Crop, CropClassification.crop_id == Crop.id)
                .join(
                    ReviewAction,
                    ReviewAction.classification_id == CropClassification.id,
                )
                .group_by(Crop.species)
            ).all()
        )

        labeled_by_species = dict(
            self.session.execute(
                select(Identity.species, func.count())
                .select_from(EmbeddingExample)
                .join(Identity, EmbeddingExample.identity_id == Identity.id)
                .group_by(Identity.species)
            ).all()
        )

        breakdown = []

        for species in Species:
            eligible_count = eligible_by_species.get(species, 0)
            confident_count = confident_by_species.get(species, 0)

            breakdown.append(
                SpeciesMetrics(
                    species=species.value,
                    eligible_count=eligible_count,
                    confident_count=confident_count,
                    unknown_count=unknown_by_species.get(species, 0),
                    reviewed_count=reviewed_by_species.get(species, 0),
                    labeled_example_count=labeled_by_species.get(species, 0),
                    coverage=(confident_count / eligible_count)
                    if eligible_count
                    else None,
                )
            )

        return breakdown

    def _count(self, query) -> int:
        return self.session.scalar(query) or 0
