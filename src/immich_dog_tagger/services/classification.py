"""
Crop classification pipeline.
"""

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClassificationMode
from immich_dog_tagger.models import (
    ClassificationSources,
    Crop,
    CropClassification,
    Detection,
)
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder
from immich_dog_tagger.policy import DEFAULT_POLICY, ClassifierPolicy
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService
from immich_dog_tagger.services.rejections import rejected_identities_for

logger = logging.getLogger(__name__)

# Both the query-and-embed chunk size and the commit checkpoint (issue
# #104/#111): each chunk is selected, embedded, and committed as one unit,
# so should_cancel() (issue #111) is only ever checked between chunks, never
# mid-chunk -- keeping this small bounds both how long a single
# embed_batch() call runs uninterruptibly and how long SQLite's write lock
# is held, so a concurrent cancel request doesn't have to wait past the
# busy_timeout. Smaller than detect's BATCH_SIZE=50 since classifying does
# comparable-or-more per-item DB work (a classification row plus an
# occurrence sync, each with their own queries) per unit of embedding cost.
BATCH_SIZE = 25


@dataclass
class ClassificationSummary:
    classified: int
    identities: dict[str, int]


class ClassificationService:
    def __init__(
        self,
        session: Session,
        embedder: OpenClipEmbedder,
        classifier: IdentityClassifier,
        policy: ClassifierPolicy = DEFAULT_POLICY,
    ):
        self.session = session
        self.embedder = embedder
        self.classifier = classifier
        self.policy = policy
        self.occurrences = PetOccurrenceService(session)

    def classify(
        self,
        mode: ClassificationMode = ClassificationMode.PENDING,
        limit: int | None = None,
        threshold: float | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ClassificationSummary:
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )

        total = 0
        counts = Counter()
        remaining = limit
        last_id = 0

        # Selects, embeds, and commits one BATCH_SIZE-sized chunk at a time
        # (issue #111) rather than embedding every eligible crop up front --
        # for a `mode=ALL`/`LOW_CONFIDENCE` run a crop can still match the
        # query's own filter after being reclassified (e.g. it's still low
        # confidence), so `Crop.id > last_id` is what guarantees each chunk
        # makes forward progress, not the mode's WHERE clause narrowing on
        # its own the way PENDING's does.
        while True:
            if should_cancel and should_cancel():
                break

            chunk_size = BATCH_SIZE if remaining is None else min(BATCH_SIZE, remaining)

            if chunk_size <= 0:
                break

            crops = (
                self._classification_query(mode, threshold)
                .filter(Crop.id > last_id)
                .order_by(Crop.id)
                .limit(chunk_size)
                .all()
            )

            if not crops:
                break

            embeddings = self.embedder.embed_batch(
                [crop.path for crop in crops],
            )

            # One query per batch, not per crop -- see rejections.py.
            rejections = rejected_identities_for(
                self.session,
                [crop.id for crop in crops],
            )

            try:
                for crop, embedding in zip(crops, embeddings):
                    classification = self._classify_crop(
                        crop,
                        embedding,
                        threshold,
                        excluded_identities=rejections.get(crop.id),
                    )

                    if classification.identity:
                        counts[classification.identity] += 1
                    else:
                        counts["Unknown"] += 1
            except Exception:
                # Discard the still-uncommitted chunk before propagating --
                # otherwise the caller's own failure-handling commit (job
                # status update, sharing this same session) would silently
                # persist it anyway, defeating the point of batching commits
                # in the first place (issue #104).
                self.session.rollback()
                raise

            self._commit(len(crops))

            total += len(crops)
            last_id = crops[-1].id

            if remaining is not None:
                remaining -= chunk_size

        if total == 0:
            logger.info("Classify (mode=%s): no eligible crops", mode.value)
        else:
            logger.info(
                "Classify (mode=%s): classified %d crop(s), %d unknown",
                mode.value,
                total,
                counts.get("Unknown", 0),
            )

        return ClassificationSummary(
            classified=total,
            identities=dict(counts),
        )

    def _commit(
        self,
        batch_size: int,
    ) -> None:
        if batch_size == 0:
            return

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.exception(
                "Failed to commit a batch of %d classified crop(s)",
                batch_size,
            )
            raise RuntimeError(
                f"Failed to commit a batch of {batch_size} classified crop(s): {exc}"
            ) from exc

    def _classify_crop(
        self,
        crop: Crop,
        embedding,
        threshold: float,
        excluded_identities=None,
    ) -> CropClassification:
        captured_at = None

        if crop.detection is not None and crop.detection.asset is not None:
            captured_at = crop.detection.asset.captured_at

        result = self.classifier.classify(
            embedding,
            species=crop.species,
            threshold=threshold,
            captured_at=captured_at,
            excluded_identities=excluded_identities,
        )

        candidates = [
            {
                "identity": candidate.identity,
                "similarity": candidate.similarity,
                "matched_example_id": candidate.matched_example_id,
                "temporal_weight": candidate.temporal_weight,
            }
            for candidate in result.candidates
        ]

        embedding_blob = embedding_to_blob(embedding)

        if crop.classification:
            classification = crop.classification

            classification.identity = result.identity
            classification.confidence = result.similarity
            classification.matched_example_id = result.matched_example_id
            classification.candidates = candidates
            classification.classifier_version = self.policy.version
            classification.embedding = embedding_blob

        else:
            classification = CropClassification(
                crop=crop,
                identity=result.identity,
                confidence=result.similarity,
                candidates=candidates,
                matched_example_id=result.matched_example_id,
                source=ClassificationSources.AUTO,
                classifier_version=self.policy.version,
                embedding=embedding_blob,
            )

            self.session.add(classification)

        self.occurrences.sync_classification(classification)

        return classification

    def _classification_query(
        self,
        mode: ClassificationMode,
        threshold: float,
    ):
        # joinedload(Crop.detection).joinedload(Detection.asset):
        # _classify_crop() reads crop.species (derived from crop.detection.label)
        # and crop.detection.asset.captured_at (DT-1114) for every crop --
        # without this, that's an N+1 query across the whole batch.
        query = self.session.query(Crop).options(
            joinedload(Crop.detection).joinedload(Detection.asset)
        )

        if mode == ClassificationMode.LOW_CONFIDENCE:
            return query.join(CropClassification).filter(
                (CropClassification.identity.is_(None))
                | (CropClassification.confidence < threshold)
            )

        if mode == ClassificationMode.PENDING:
            return query.filter(~Crop.classification.has())

        if mode == ClassificationMode.ALL:
            return query

        raise ValueError(f"Unknown classification mode: {mode}")
