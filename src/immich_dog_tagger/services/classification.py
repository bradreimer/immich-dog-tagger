"""
Crop classification pipeline.
"""

import logging
from collections import Counter
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

logger = logging.getLogger(__name__)

# Matches PetOccurrenceService.sync_all's batch size -- classifying a crop
# does comparable per-item DB work (a classification row plus an occurrence
# sync, each involving their own queries). A single commit at the end of the
# whole batch held state.db's write lock for the run's entire duration,
# blocking every other reader (issue #104); see scanner.BATCH_SIZE/issue #99
# for the same fix applied to `scan`.
BATCH_SIZE = 500


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
    ) -> ClassificationSummary:
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )
        query = self._classification_query(
            mode,
            threshold,
        )

        if limit is not None:
            query = query.limit(limit)

        crops = query.all()

        if not crops:
            logger.info("Classify (mode=%s): no eligible crops", mode.value)
            return ClassificationSummary(
                classified=0,
                identities={},
            )

        counts = Counter()

        embeddings = self.embedder.embed_batch(
            [crop.path for crop in crops],
        )

        since_commit = 0

        try:
            for crop, embedding in zip(crops, embeddings):
                classification = self._classify_crop(
                    crop,
                    embedding,
                    threshold,
                )

                if classification.identity:
                    counts[classification.identity] += 1
                else:
                    counts["Unknown"] += 1

                since_commit += 1

                if since_commit >= BATCH_SIZE:
                    self._commit(since_commit)
                    since_commit = 0
        except Exception:
            # Discard the still-uncommitted batch before propagating --
            # otherwise the caller's own failure-handling commit (job status
            # update, sharing this same session) would silently persist it
            # anyway, defeating the point of batching commits in the first
            # place (issue #104).
            self.session.rollback()
            raise

        self._commit(since_commit)

        logger.info(
            "Classify (mode=%s): classified %d crop(s), %d unknown",
            mode.value,
            len(crops),
            counts.get("Unknown", 0),
        )

        return ClassificationSummary(
            classified=len(crops),
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
    ) -> CropClassification:
        captured_at = None

        if crop.detection is not None and crop.detection.asset is not None:
            captured_at = crop.detection.asset.captured_at

        result = self.classifier.classify(
            embedding,
            species=crop.species,
            threshold=threshold,
            captured_at=captured_at,
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
