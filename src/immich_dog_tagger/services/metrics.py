"""
Learning-progress metrics.

Answers the question v1.0.0 exists to answer: is manual review becoming
less necessary? Every count states its own denominator/scope explicitly
(see LearningMetrics fields) rather than presenting a bare percentage.
Precision/accuracy are intentionally not computed here -- they would
require a held-out evaluation set distinct from the reviews used as
ground truth, which does not exist in v1.0.0.
"""

from collections import Counter
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
    PetOccurrence,
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
    crop legitimately contain no pet. `with_dog_rate`/`with_cat_rate`
    answer exactly one question each -- of the photos detection has
    finished with, what share produced at least one crop of that species.

    Split by species (rather than one combined "has a pet crop" figure)
    since a photo with both a dog and a cat should count toward both, and
    an owner watching coverage for one species should not have that
    figure diluted by the other.
    """

    # Every asset row the scanner knows about, whatever stage it reached.
    scanned_count: int
    # The stated denominator: photos detection has finished with.
    processed_count: int
    with_dog_count: int
    with_dog_rate: float | None
    with_cat_count: int
    with_cat_rate: float | None
    # Scanned but not yet through detection -- not evidence of anything
    # missed, just work the pipeline still has queued.
    awaiting_detection_count: int
    # Cannot reach detection without operator action (failed download or
    # detection, unsupported file type).
    unprocessable_count: int


_SEASON_BY_MONTH: dict[int, str] = {
    12: "Winter",
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Fall",
    10: "Fall",
    11: "Fall",
}
# Chronological order *starting from Spring*, not Winter -- Winter is
# labeled by the December that starts it (see _season_bucket) but actually
# spans into Jan/Feb of the following calendar year, so the season that
# chronologically follows "Winter Y" is "Spring (Y+1)", not "Spring Y".
# Starting the sequence at Spring makes each season's (year, index) sort key
# increase monotonically with real time, which the wraparound in
# _next_season_bucket and the ordering in _season_sort_key both depend on.
_SEASON_SEQUENCE = ("Spring", "Summer", "Fall", "Winter")

# How many pet identities get their own stacked band on a species timeline
# chart before the rest are folded into a single "Other" band -- sized to
# this app's validated 5-color categorical chart palette (--chart-1..5,
# DT-1104: one band per top identity plus one for "Other"), not an
# arbitrary cutoff (issue #271).
TOP_N_TIMELINE_IDENTITIES = 4


def _season_bucket(captured_at: datetime) -> tuple[int, str]:
    """
    (year, season) such that sorting by _season_sort_key() is chronological.
    Winter spans a calendar-year boundary, so it's labeled by the December's
    year -- Dec 2025 and Jan/Feb 2026 both bucket to (2025, "Winter"),
    matching the "meteorological winter is named for the year it starts"
    convention.
    """
    season = _SEASON_BY_MONTH[captured_at.month]
    year = captured_at.year - 1 if captured_at.month in (1, 2) else captured_at.year
    return (year, season)


def _next_season_bucket(bucket: tuple[int, str]) -> tuple[int, str]:
    year, season = bucket
    index = _SEASON_SEQUENCE.index(season)
    if index == len(_SEASON_SEQUENCE) - 1:
        return (year + 1, _SEASON_SEQUENCE[0])
    return (year, _SEASON_SEQUENCE[index + 1])


def _season_sort_key(bucket: tuple[int, str]) -> tuple[int, int]:
    year, season = bucket
    return (year, _SEASON_SEQUENCE.index(season))


@dataclass(frozen=True)
class SpeciesTimelinePoint:
    label: str
    counts: dict[str, int]


@dataclass(frozen=True)
class SpeciesTimeline:
    species: str
    # Stacking order: top identities by total volume, "Other" last if present.
    identities: list[str]
    points: list[SpeciesTimelinePoint]


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
        crops grouped by species. No per-asset query and no row-by-row
        Python loop, so this stays as cheap at 30,000 photos as at 30.

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
        # old crops, and counting those here would let a with_*_count
        # exceed processed_count.
        with_species_count = dict(
            self.session.execute(
                select(Crop.species, func.count(func.distinct(Detection.asset_id)))
                .select_from(Crop)
                .join(Detection, Crop.detection_id == Detection.id)
                .join(Asset, Detection.asset_id == Asset.id)
                .where(Asset.status.in_(DETECTION_COMPLETE_STATUSES))
                .group_by(Crop.species)
            ).all()
        )
        with_dog_count = with_species_count.get(Species.DOG, 0)
        with_cat_count = with_species_count.get(Species.CAT, 0)

        return DetectionCoverage(
            scanned_count=scanned_count,
            processed_count=processed_count,
            with_dog_count=with_dog_count,
            with_dog_rate=(with_dog_count / processed_count)
            if processed_count
            else None,
            with_cat_count=with_cat_count,
            with_cat_rate=(with_cat_count / processed_count)
            if processed_count
            else None,
            awaiting_detection_count=total(DETECTION_PENDING_STATUSES),
            unprocessable_count=total(DETECTION_BLOCKED_STATUSES),
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

    def species_timeline(self, species: Species) -> SpeciesTimeline:
        """
        Confirmed-photo volume for one species, bucketed by season and
        stacked by individual pet identity (issue #271) -- keyed off
        `PetOccurrence`/`Asset.captured_at`, the same "when was this photo
        taken" concept the Insights page's time-based facts already use
        (`MostActiveMonthProvider` et al.), not `Asset.created_at` (pipeline
        ingestion time, a different concept `_detection_coverage()` covers).

        One flat query, all bucketing/ranking done in Python: a per-season,
        per-identity SQL GROUP BY would need season bucketing expressed in
        SQL, awkward for Winter's year rollover, and the row count here is
        bounded by "confirmed photos of this species" -- the same order of
        magnitude an InsightProvider already loads fully into Python for one
        identity, just for every identity of one species here instead.
        """
        rows = self.session.execute(
            select(Asset.captured_at, Identity.id, Identity.name)
            .select_from(PetOccurrence)
            .join(Asset, PetOccurrence.asset_id == Asset.id)
            .join(Identity, PetOccurrence.identity_id == Identity.id)
            .where(Identity.species == species, Asset.captured_at.is_not(None))
        ).all()

        if not rows:
            return SpeciesTimeline(species=species.value, identities=[], points=[])

        totals: Counter[tuple[int, str]] = Counter()
        counts_by_bucket: dict[tuple[int, str], Counter[tuple[int, str]]] = {}

        for captured_at, identity_id, identity_name in rows:
            bucket = _season_bucket(captured_at)
            identity_key = (identity_id, identity_name)
            totals[identity_key] += 1
            counts_by_bucket.setdefault(bucket, Counter())[identity_key] += 1

        # Ties break on the lower identity_id, matching BestFriendProvider's
        # deterministic tiebreak for the same kind of "top by count" ranking.
        ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0][0]))
        top_identities = ranked[:TOP_N_TIMELINE_IDENTITIES]
        top_ids = {identity_id for (identity_id, _), _ in top_identities}
        identities = [name for (_, name), _ in top_identities]

        if len(ranked) > len(top_identities):
            identities.append("Other")

        sorted_buckets = sorted(counts_by_bucket, key=_season_sort_key)
        first_bucket, last_bucket = sorted_buckets[0], sorted_buckets[-1]

        all_buckets = []
        bucket = first_bucket
        while _season_sort_key(bucket) <= _season_sort_key(last_bucket):
            all_buckets.append(bucket)
            bucket = _next_season_bucket(bucket)

        points = []

        for bucket in all_buckets:
            counts = dict.fromkeys(identities, 0)

            for (identity_id, identity_name), count in counts_by_bucket.get(
                bucket, {}
            ).items():
                key = identity_name if identity_id in top_ids else "Other"
                counts[key] += count

            points.append(
                SpeciesTimelinePoint(label=f"{bucket[1]} {bucket[0]}", counts=counts)
            )

        return SpeciesTimeline(
            species=species.value, identities=identities, points=points
        )

    def _count(self, query) -> int:
        return self.session.scalar(query) or 0
