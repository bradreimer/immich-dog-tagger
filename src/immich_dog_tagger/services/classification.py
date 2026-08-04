"""
Crop classification pipeline.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.enums import ClassificationMode
from immich_dog_tagger.models import (
    ClassificationSources,
    Crop,
    CropClassification,
)
from immich_dog_tagger.openclip_embedder import OpenClipEmbedder


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
    ):
        self.session = session
        self.embedder = embedder
        self.classifier = classifier

    def classify(
        self,
        mode: ClassificationMode = ClassificationMode.PENDING,
        limit: int | None = None,
        threshold: float = 0.80,
    ) -> ClassificationSummary:
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

        if crop.classification:
            classification = crop.classification

            classification.identity = result.identity
            classification.confidence = result.similarity
            classification.matched_example_id = result.matched_example_id

        else:
            classification = CropClassification(
                crop=crop,
                identity=result.identity,
                confidence=result.similarity,
                matched_example_id=result.matched_example_id,
                source=ClassificationSources.AUTO,
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
