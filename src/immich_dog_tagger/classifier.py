"""
Dog identity classifier.
"""

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from .embeddings import blob_to_embedding
from .models import EmbeddingExample


@dataclass(frozen=True)
class ClassificationResult:
    identity: str | None
    confidence: float


class IdentityClassifier:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def classify(
        self,
        embedding: np.ndarray,
        threshold: float = 0.80,
    ) -> ClassificationResult:

        best_identity = None
        best_score = -1.0

        examples = self.session.query(EmbeddingExample).all()

        for example in examples:
            known = blob_to_embedding(example.embedding)

            score = self._cosine_similarity(
                embedding,
                known,
            )

            if score > best_score:
                best_score = score
                best_identity = example.identity.name

        if best_score < threshold:
            return ClassificationResult(
                identity=None,
                confidence=best_score,
            )

        return ClassificationResult(
            identity=best_identity,
            confidence=best_score,
        )

    def _cosine_similarity(
        self,
        a: np.ndarray,
        b: np.ndarray,
    ) -> float:

        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
