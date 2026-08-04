"""
Dog identity classifier.
"""

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from .embeddings import blob_to_embedding
from .models import EmbeddingExample
from .scoring import SimilarityScorer


@dataclass(frozen=True)
class ClassificationCandidate:
    identity: str
    similarity: float
    matched_example_id: int


@dataclass(frozen=True)
class ClassificationResult:
    identity: str | None
    similarity: float
    matched_example_id: int | None
    candidates: list[ClassificationCandidate]


class IdentityClassifier:
    def __init__(
        self,
        session: Session,
        scorer: SimilarityScorer | None = None,
    ):
        self.session = session
        self.scorer = scorer or SimilarityScorer()

    def classify(
        self,
        embedding: np.ndarray,
        threshold: float = 0.80,
        candidate_limit: int = 3,
    ) -> ClassificationResult:

        identity_scores: dict[str, ClassificationCandidate] = {}

        examples = self.session.query(EmbeddingExample).all()

        for example in examples:
            known = blob_to_embedding(example.embedding)

            similarity = self._cosine_similarity(
                embedding,
                known,
            )

            score = self.scorer.score(
                similarity,
            )

            candidate = ClassificationCandidate(
                identity=example.identity.name,
                similarity=score.similarity,
                matched_example_id=example.id,
            )

            existing = identity_scores.get(candidate.identity)

            if existing is None or candidate.similarity > existing.similarity:
                identity_scores[candidate.identity] = candidate

        candidates = list(identity_scores.values())

        candidates.sort(
            key=lambda candidate: candidate.similarity,
            reverse=True,
        )

        top_candidates = candidates[:candidate_limit]

        if not top_candidates:
            return ClassificationResult(
                identity=None,
                similarity=-1.0,
                matched_example_id=None,
                candidates=[],
            )

        best = top_candidates[0]

        if best.similarity < threshold:
            return ClassificationResult(
                identity=None,
                similarity=best.similarity,
                matched_example_id=best.matched_example_id,
                candidates=top_candidates,
            )

        return ClassificationResult(
            identity=best.identity,
            similarity=best.similarity,
            matched_example_id=best.matched_example_id,
            candidates=top_candidates,
        )

    def _cosine_similarity(
        self,
        a: np.ndarray,
        b: np.ndarray,
    ) -> float:

        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
