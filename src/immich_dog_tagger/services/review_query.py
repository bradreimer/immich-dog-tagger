from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session, selectinload

from immich_dog_tagger.classifier import ClassificationCandidate
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
_REVIEW_ITEM_RELATIONSHIPS = (
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
_LIBRARY_RELATIONSHIPS = _REVIEW_ITEM_RELATIONSHIPS + (
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
            .options(*_REVIEW_ITEM_RELATIONSHIPS)
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
            .options(*_REVIEW_ITEM_RELATIONSHIPS)
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
        limit: int = 50,
        offset: int = 0,
    ) -> LibraryPage:
        """
        Every classified photo, reviewed and unreviewed alike -- unlike
        `active_review()`, this never excludes already-reviewed items. The
        library is a browsable catalogue, not a queue that empties out.
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

        query = (
            select(CropClassification)
            .options(*_LIBRARY_RELATIONSHIPS)
            .order_by(CropClassification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        for condition in filters:
            query = query.where(condition)

        classifications = self.session.scalars(query).all()

        return LibraryPage(
            items=[self._to_library_entry(c) for c in classifications],
            total=total,
            limit=limit,
            offset=offset,
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
        )

    def _captured_at(
        self,
        classification: CropClassification,
    ) -> datetime | None:
        detection = classification.crop.detection

        if detection is None or detection.asset is None:
            return None

        return detection.asset.captured_at

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

        if classification.candidates:
            return "candidate-conflict"

        if decision is ClassificationDecision.NEEDS_REVIEW:
            return "low-confidence"

        return "review"
