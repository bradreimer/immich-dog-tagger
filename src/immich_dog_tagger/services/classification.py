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

        for crop in crops:
            embedding = self.embedder.embed(
                crop.path,
            )

            result = self.classifier.classify(
                embedding,
            )

            if result.identity:
                counts[result.identity] += 1
            else:
                counts["Unknown"] += 1

            classification = CropClassification(
                crop=crop,
                identity=result.identity,
                confidence=result.confidence,
                matched_example_id=result.matched_example_id,
            )

            self.session.add(classification)

        self.session.commit()

        return ClassificationSummary(
            classified=len(crops),
            identities=dict(counts),
        )
