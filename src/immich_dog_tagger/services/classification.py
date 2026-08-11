"""
Crop classification pipeline.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClassificationMode
from immich_dog_tagger.models import (
    ClassificationSources,
    Crop,
    CropClassification,
)
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder
from immich_dog_tagger.policy import DEFAULT_POLICY, ClassifierPolicy


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
            return ClassificationSummary(
                classified=0,
                identities={},
            )

        counts = Counter()

        embeddings = self.embedder.embed_batch(
            [crop.path for crop in crops],
        )

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

        self.session.commit()

        return ClassificationSummary(
            classified=len(crops),
            identities=dict(counts),
        )

    def _classify_crop(
        self,
        crop: Crop,
        embedding,
        threshold: float,
    ) -> CropClassification:
        result = self.classifier.classify(
            embedding,
            threshold=threshold,
        )

        candidates = [
            {
                "identity": candidate.identity,
                "similarity": candidate.similarity,
                "matched_example_id": candidate.matched_example_id,
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

        return classification

    def _classification_query(
        self,
        mode: ClassificationMode,
        threshold: float,
    ):
        query = self.session.query(Crop)

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
