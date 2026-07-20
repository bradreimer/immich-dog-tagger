"""
Crop classification pipeline.
"""

from sqlalchemy.orm import Session

from .classifier import IdentityClassifier
from .models import Crop
from .openclip_embedder import OpenClipEmbedder


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
    ) -> int:
        query = self.session.query(Crop).filter(~Crop.classification.has())

        if limit is not None:
            query = query.limit(limit)

        crops = query.all()

        for crop in crops:
            embedding = self.embedder.embed(
                crop.path,
            )

            result = self.classifier.classify(
                embedding,
            )

            from .models import CropClassification

            classification = CropClassification(
                crop=crop,
                identity=result.identity,
                confidence=result.confidence,
            )

            self.session.add(classification)

        self.session.commit()

        return len(crops)
