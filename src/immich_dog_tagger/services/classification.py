"""
Crop classification pipeline.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.models import Crop, CropClassification
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

    def classify_pending(
        self,
        limit: int | None = None,
    ) -> ClassificationSummary:
        query = self.session.query(Crop).filter(~Crop.classification.has())

        if limit is not None:
            query = query.limit(limit)

        crops = query.all()

        counts = Counter()

        embeddings = self.embedder.embed_batch(
            [crop.path for crop in crops],
        )

        for crop, embedding in zip(crops, embeddings):
            classification = self._classify_crop(
                crop,
                embedding,
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
    ) -> CropClassification:
        result = self.classifier.classify(
            embedding,
        )

        if crop.classification:
            classification = crop.classification

            classification.identity = result.identity
            classification.confidence = result.confidence
            classification.matched_example_id = result.matched_example_id

        else:
            classification = CropClassification(
                crop=crop,
                identity=result.identity,
                confidence=result.confidence,
                matched_example_id=result.matched_example_id,
            )

            self.session.add(classification)

        return classification
