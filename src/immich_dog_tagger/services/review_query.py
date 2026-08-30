from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session, selectinload

from immich_dog_tagger.classifier import ClassificationCandidate
from immich_dog_tagger.enums import ClusterSort
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    ReviewAction,
)

# Eager-load the relationships _to_review_item() touches (crop, the crop's
# detection -- for crop.species, DT-1110 -- and the detection's asset -- for
# the photo's own capture date, DT-1111 -- plus the matched example and the
# example's identity) so a review-queue page issues a constant number of
# queries instead of one extra round trip per row.
REVIEW_ITEM_RELATIONSHIPS = (
    selectinload(CropClassification.crop)
    .selectinload(Crop.detection)
    .selectinload(Detection.asset),
    selectinload(CropClassification.matched_example).selectinload(
        EmbeddingExample.identity
    ),
)

# The library (DT-1112) additionally needs each classification's review
# actions to compute reviewed/reviewed_at -- something the queue views never
# surface, since they only ever show unreviewed items.
_LIBRARY_RELATIONSHIPS = REVIEW_ITEM_RELATIONSHIPS + (
    selectinload(CropClassification.review_actions),
)
from immich_dog_tagger.policy import (
    DEFAULT_POLICY,
    ClassificationDecision,
    ClassifierPolicy,
)

# v1.5/ADR-003: below this, a match's example is far enough out of alignment
# with the photo's own capture date (roughly beyond a year and a half, given
# scoring.TEMPORAL_SIGMA_DAYS/TEMPORAL_FLOOR) that it's worth surfacing to
# the owner as a reason to double check, rather than presenting it as a
# routine match.
_TEMPORAL_MISMATCH_THRESHOLD = 0.5

# v1.9/ADR-007: the same treatment as _TEMPORAL_MISMATCH_THRESHOLD, for how
# far a match's example was taken from the photo's own location (roughly
# beyond ~2.7km, given scoring.SPATIAL_SIGMA_KM/SPATIAL_FLOOR).
_SPATIAL_MISMATCH_THRESHOLD = 0.5


@dataclass(frozen=True)
class ReviewPrediction:
    identity: str | None
    similarity: float
    candidates: list[ClassificationCandidate]


@dataclass(frozen=True)
class ReviewSuggestion:
    identity: str
    similarity: float
    example_id: int
    example_path: Path
    captured_at: datetime | None


@dataclass(frozen=True)
class ReviewItem:
    classification_id: int
    crop_id: int
    path: Path
    species: str
    prediction: ReviewPrediction
    suggestion: ReviewSuggestion | None
    captured_at: datetime | None = None
    reason: str = "review"
    # The Immich asset the crop came from, so the UI can deep link to the
    # original photo. None whenever the detection or asset is missing --
    # the same fail-open stance _captured_at() takes.
    immich_asset_id: str | None = None
    # "city, state, country" from the same cached Asset fields Insights
    # reads (issue #94/#129), joined on whichever parts are present. None
    # when the asset is missing or has no location data at all.
    location: str | None = None
    # A human's "not a dog or cat" flag on the underlying crop (issue #185),
    # surfaced so the Library/Review UI can render its current state.
    not_animal: bool = False

    @property
    def filename(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ReviewSummary:
    total: int
    identities: dict[str, int]
    unknown: int
    confidence_buckets: dict[str, int]


@dataclass(frozen=True)
class ReviewQueueStats:
    total: int
    reviewed: int
    remaining: int


@dataclass(frozen=True)
class LibraryEntry:
    item: ReviewItem
    reviewed: bool
    reviewed_at: datetime | None


@dataclass(frozen=True)
class LibraryPage:
    items: list[LibraryEntry]
    total: int
    limit: int
    offset: int


class ReviewQueryService:
    def __init__(
        self,
        session: Session,
        policy: ClassifierPolicy = DEFAULT_POLICY,
    ):
        self.session = session
        self.policy = policy

    def item_for_classification(
        self,
        classification_id: int,
    ) -> ReviewItem | None:
        """
        Build a single ReviewItem for a classification that was just
        mutated elsewhere (e.g. a species correction) and needs to be
        reflected back to the caller without a full queue reload.
        """
        classification = self.session.scalars(
            select(CropClassification)
            .options(*REVIEW_ITEM_RELATIONSHIPS)
            .where(CropClassification.id == classification_id)
        ).first()

        if classification is None:
            return None

        return self._to_review_item(classification)

    def review_item(
        self,
        classification: CropClassification,
    ) -> ReviewItem:
        """
        Build the ReviewItem view model for a classification the caller has
        already loaded (with REVIEW_ITEM_RELATIONSHIPS eager-loaded, or it
        pays a round trip per relationship). Lets other read-side services
        -- clustering, issue #141 -- present classifications in exactly the
        shape the review and library surfaces already render, instead of
        each growing its own view model.
        """
        return self._to_review_item(classification)

    def classifications(
        self,
        *,
        limit: int | None = None,
        identity: str | None = None,
        unknown: bool = False,
        confidence_below: float | None = None,
    ) -> list[ReviewItem]:

        if unknown and identity is not None:
            raise ValueError("identity and unknown cannot be combined")

        query = (
            select(CropClassification)
            .options(*REVIEW_ITEM_RELATIONSHIPS)
            .order_by(CropClassification.confidence.asc())
        )

        if unknown:
            query = query.where(CropClassification.identity.is_(None))

        if identity is not None:
            query = query.where(CropClassification.identity == identity)

        if confidence_below is not None:
            query = query.where(CropClassification.confidence < confidence_below)

        if limit is not None:
            query = query.limit(limit)

        classifications = self.session.scalars(query).all()

        return [
            self._to_review_item(classification) for classification in classifications
        ]

    def summary(self) -> ReviewSummary:
        query = select(CropClassification)

        classifications = self.session.scalars(query).all()

        total = len(classifications)

        identities = Counter()
        unknown = 0

        confidence_buckets = {
            "<0.80": 0,
            "0.80-0.90": 0,
            ">0.90": 0,
        }

        for classification in classifications:
            if classification.identity:
                identities[classification.identity] += 1
            else:
                unknown += 1

            if classification.confidence < 0.80:
                confidence_buckets["<0.80"] += 1
            elif classification.confidence < 0.90:
                confidence_buckets["0.80-0.90"] += 1
            else:
                confidence_buckets[">0.90"] += 1

        return ReviewSummary(
            total=total,
            identities=dict(identities),
            unknown=unknown,
            confidence_buckets=dict(confidence_buckets),
        )

    def review_queue_stats(self) -> ReviewQueueStats:
        total = self.session.scalar(
            select(func.count()).select_from(CropClassification)
        )

        reviewed = self.session.scalar(
            select(func.count())
            .select_from(CropClassification)
            .where(
                self._has_review_action(),
            )
        )

        return ReviewQueueStats(
            total=total or 0,
            reviewed=reviewed or 0,
            # Bug fix: this used to be `total - reviewed`, which counts
            # every unreviewed classification -- including ones that are
            # confidently auto-classified and were never going to need a
            # human to look at them. That made the Mission Control banner
            # and sidebar badge (both driven by this field) claim "N images
            # need review" while the actual /review queue, correctly
            # filtered by review_queue_count(), showed nothing to review.
            # remaining must mean the same thing everywhere it's surfaced:
            # how many items active_review() would actually return.
            remaining=self.review_queue_count(),
        )

    def review_queue_count(
        self,
        *,
        threshold: float | None = None,
    ) -> int:
        """
        Count of items `active_review()` would actually surface as pending
        work: no review action yet, and either unknown or below the
        confident threshold. This excludes confidently-classified items
        that simply haven't been manually reviewed yet -- those don't need
        a human to look at them. `review_queue_stats().remaining` reuses
        this method for exactly that reason, rather than the naive `total
        minus reviewed` it used to compute.
        """
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )

        query = (
            select(func.count())
            .select_from(CropClassification)
            .where(~self._has_review_action())
            .where(
                (CropClassification.identity.is_(None))
                | (CropClassification.confidence < threshold)
            )
        )

        return self.session.scalar(query) or 0

    def active_review(
        self,
        *,
        threshold: float | None = None,
        limit: int | None = None,
        unknown: bool = False,
        confidence_below: float | None = None,
        candidate_conflict: bool = False,
    ) -> list[ReviewItem]:
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )

        priority = case(
            (
                CropClassification.identity.is_(None),
                0,
            ),
            else_=1,
        )

        query = (
            select(CropClassification)
            .options(*REVIEW_ITEM_RELATIONSHIPS)
            .where(
                ~self._has_review_action(),
            )
            .where(
                (CropClassification.identity.is_(None))
                | (CropClassification.confidence < threshold)
            )
            .order_by(
                priority.asc(),
                CropClassification.confidence.asc(),
                CropClassification.created_at.asc(),
            )
        )

        if limit is not None:
            query = query.limit(limit)

        if unknown:
            query = query.where(CropClassification.identity.is_(None))

        if confidence_below is not None:
            query = query.where(CropClassification.confidence < confidence_below)

        if candidate_conflict:
            query = query.where(CropClassification.candidates != [])

        classifications = self.session.scalars(query).all()

        return [
            self._to_review_item(classification) for classification in classifications
        ]

    def library(
        self,
        *,
        identity: str | None = None,
        species: str | None = None,
        reviewed: bool | None = None,
        captured_after: datetime | None = None,
        captured_before: datetime | None = None,
        sort: ClusterSort = ClusterSort.CAPTURED_DESC,
        limit: int = 50,
        offset: int = 0,
    ) -> LibraryPage:
        """
        Every classified photo, reviewed and unreviewed alike -- unlike
        `active_review()`, this never excludes already-reviewed items. The
        library is a browsable catalogue, not a queue that empties out.

        `sort` reuses `ClusterSort` (v1.11): unlike clustering, which sorts a
        single bounded in-memory pool, the library paginates over a
        potentially large filtered set, so ordering is applied in SQL before
        LIMIT/OFFSET rather than after fetching a page.
        """
        filters = self._library_filters(
            identity=identity,
            species=species,
            reviewed=reviewed,
            captured_after=captured_after,
            captured_before=captured_before,
        )

        count_query = select(func.count()).select_from(CropClassification)

        for condition in filters:
            count_query = count_query.where(condition)

        total = self.session.scalar(count_query) or 0

        query = select(CropClassification).options(*_LIBRARY_RELATIONSHIPS)
        query = self._order_library(query, sort)
        query = query.limit(limit).offset(offset)

        for condition in filters:
            query = query.where(condition)

        classifications = self.session.scalars(query).all()

        return LibraryPage(
            items=[self._to_library_entry(c) for c in classifications],
            total=total,
            limit=limit,
            offset=offset,
        )

    def _order_library(self, query, sort: ClusterSort):
        if sort in (ClusterSort.CONFIDENCE_DESC, ClusterSort.CONFIDENCE_ASC):
            return query.order_by(
                CropClassification.confidence.desc()
                if sort is ClusterSort.CONFIDENCE_DESC
                else CropClassification.confidence.asc(),
                CropClassification.id.asc(),
            )

        # Captured-date sort: a correlated scalar subquery rather than a
        # join, so a classification's row identity (and the count query
        # above, which shares no join) is never at risk of duplicating.
        captured_at = (
            select(Asset.captured_at)
            .select_from(Crop)
            .join(Detection, Detection.id == Crop.detection_id)
            .join(Asset, Asset.id == Detection.asset_id)
            .where(Crop.id == CropClassification.crop_id)
            .correlate(CropClassification)
            .scalar_subquery()
        )

        # Undated photos sort last under both directions (the same
        # convention RecommendationClusterService uses), then a stable id
        # tiebreak so equal dates never reorder between requests.
        return query.order_by(
            captured_at.is_(None).asc(),
            captured_at.desc()
            if sort is ClusterSort.CAPTURED_DESC
            else captured_at.asc(),
            CropClassification.id.asc(),
        )

    def _library_filters(
        self,
        *,
        identity: str | None,
        species: str | None,
        reviewed: bool | None,
        captured_after: datetime | None,
        captured_before: datetime | None,
    ) -> list:
        filters = []

        if identity is not None:
            filters.append(CropClassification.identity == identity)

        if species is not None:
            filters.append(CropClassification.crop.has(Crop.species == species))

        if reviewed is not None:
            condition = self._has_review_action()
            filters.append(condition if reviewed else ~condition)

        if captured_after is not None:
            filters.append(
                CropClassification.crop.has(
                    Crop.detection.has(
                        Detection.asset.has(Asset.captured_at >= captured_after)
                    )
                )
            )

        if captured_before is not None:
            filters.append(
                CropClassification.crop.has(
                    Crop.detection.has(
                        Detection.asset.has(Asset.captured_at <= captured_before)
                    )
                )
            )

        return filters

    def _to_library_entry(
        self,
        classification: CropClassification,
    ) -> LibraryEntry:
        review_actions = classification.review_actions
        reviewed_at = max(
            (action.created_at for action in review_actions),
            default=None,
        )

        return LibraryEntry(
            item=self._to_review_item(classification),
            reviewed=len(review_actions) > 0,
            reviewed_at=reviewed_at,
        )

    def _candidates(
        self,
        classification: CropClassification,
    ) -> list[ClassificationCandidate]:
        return [
            ClassificationCandidate(
                identity=candidate["identity"],
                similarity=candidate["similarity"],
                matched_example_id=candidate.get(
                    "matched_example_id",
                    -1,
                ),
                # Absent on candidates stored before v1.5/ADR-003 (or under
                # the old date_conflict key) -- read as full alignment, the
                # same fail-open default the field itself has.
                temporal_weight=candidate.get("temporal_weight", 1.0),
                # Absent on candidates stored before v1.9/ADR-007 -- same
                # fail-open default.
                spatial_weight=candidate.get("spatial_weight", 1.0),
            )
            for candidate in classification.candidates
        ]

    def _prediction(
        self,
        classification: CropClassification,
    ) -> ReviewPrediction:
        return ReviewPrediction(
            identity=classification.identity,
            similarity=classification.confidence,
            candidates=self._candidates(classification),
        )

    def _suggestion(
        self,
        classification: CropClassification,
    ) -> ReviewSuggestion | None:
        example = classification.matched_example

        if example is None:
            return None

        return ReviewSuggestion(
            identity=example.identity.name,
            similarity=classification.confidence,
            example_id=example.id,
            example_path=Path(example.crop_path),
            captured_at=example.captured_at,
        )

    def _to_review_item(
        self,
        classification: CropClassification,
    ) -> ReviewItem:
        return ReviewItem(
            classification_id=classification.id,
            crop_id=classification.crop.id,
            path=Path(classification.crop.path),
            species=classification.crop.species,
            prediction=self._prediction(classification),
            suggestion=self._suggestion(classification),
            captured_at=self._captured_at(classification),
            reason=self._review_reason(classification),
            immich_asset_id=self._immich_asset_id(classification),
            location=self._location(classification),
            not_animal=classification.crop.not_animal,
        )

    def _captured_at(
        self,
        classification: CropClassification,
    ) -> datetime | None:
        detection = classification.crop.detection

        if detection is None or detection.asset is None:
            return None

        return detection.asset.captured_at

    def _immich_asset_id(
        self,
        classification: CropClassification,
    ) -> str | None:
        detection = classification.crop.detection

        if detection is None or detection.asset is None:
            return None

        return detection.asset.immich_asset_id

    def _location(
        self,
        classification: CropClassification,
    ) -> str | None:
        detection = classification.crop.detection

        if detection is None or detection.asset is None:
            return None

        asset = detection.asset
        parts = [part for part in (asset.city, asset.state, asset.country) if part]

        return ", ".join(parts) if parts else None

    def _has_review_action(self):
        return exists(
            select(ReviewAction.id).where(
                ReviewAction.classification_id == CropClassification.id,
            )
        )

    def _review_reason(
        self,
        classification: CropClassification,
    ) -> str:
        decision = self.policy.decide(
            identity=classification.identity,
            similarity=classification.confidence,
        )

        if decision is ClassificationDecision.UNKNOWN:
            return "unknown"

        # The top candidate is always classification.candidates[0] (see
        # IdentityClassifier.classify()'s sort-then-slice), and is the
        # accepted identity whenever one was accepted -- so this single
        # check covers both "the accepted identity's match is temporally
        # weak" and "the top candidate's is" (v1.5/ADR-003). A weight of 1.0
        # -- whether the dates aligned or a date was simply missing -- never
        # triggers this, preserving the fail-open guarantee.
        if (
            classification.candidates
            and classification.candidates[0].get("temporal_weight", 1.0)
            < _TEMPORAL_MISMATCH_THRESHOLD
        ):
            return "temporal-mismatch"

        # v1.9/ADR-007: same precedent as temporal-mismatch above, for
        # location. Checked second -- an item with both a temporal and a
        # spatial mismatch reports temporal-mismatch, per this pass's Open
        # Questions (v1.9-automatic-spatial-classification.md).
        if (
            classification.candidates
            and classification.candidates[0].get("spatial_weight", 1.0)
            < _SPATIAL_MISMATCH_THRESHOLD
        ):
            return "location-mismatch"

        if classification.candidates:
            return "candidate-conflict"

        if decision is ClassificationDecision.NEEDS_REVIEW:
            return "low-confidence"

        return "review"
