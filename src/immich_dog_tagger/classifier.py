"""
Dog identity classifier.
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session, contains_eager

from .embeddings import blob_to_embedding
from .enums import Species
from .models import EmbeddingExample, Identity
from .policy import DEFAULT_POLICY, ClassifierPolicy
from .scoring import SimilarityScorer


@dataclass(frozen=True)
class ClassificationCandidate:
    identity: str
    similarity: float
    matched_example_id: int
    # DT-1114: True when the crop's capture date falls outside this
    # candidate identity's known active date range -- a signal surfaced
    # alongside the match, never folded into `similarity` (which stays a
    # raw, uncalibrated embedding score; see v1.0.0.md section 8).
    date_conflict: bool = False


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
        policy: ClassifierPolicy = DEFAULT_POLICY,
    ):
        self.session = session
        self.scorer = scorer or SimilarityScorer()
        self.policy = policy
        self._examples_cache: dict[str, list[EmbeddingExample]] | None = None

    def classify(
        self,
        embedding: np.ndarray,
        species: Species = Species.DOG,
        threshold: float | None = None,
        candidate_limit: int | None = None,
        captured_at: datetime | None = None,
    ) -> ClassificationResult:
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )
        candidate_limit = (
            candidate_limit
            if candidate_limit is not None
            else self.policy.candidate_limit
        )

        identity_scores: dict[str, ClassificationCandidate] = {}

        for example in self._load_examples(species):
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
                date_conflict=self._date_conflict(captured_at, example.identity),
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

    def _date_conflict(
        self,
        captured_at: datetime | None,
        identity: Identity,
    ) -> bool:
        """
        Fail-open by design: no crop capture date, or an identity with
        neither bound set, means "no date signal available" -- never treat
        that as suspicious. Either bound alone is unbounded on that side.
        """
        if captured_at is None:
            return False

        if identity.active_from is None and identity.active_until is None:
            return False

        if identity.active_from is not None and captured_at < identity.active_from:
            return True

        return identity.active_until is not None and captured_at > identity.active_until

    def _cosine_similarity(
        self,
        a: np.ndarray,
        b: np.ndarray,
    ) -> float:

        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _load_examples(self, species: Species) -> list[EmbeddingExample]:
        """
        Load and cache active labeled examples for this classifier instance's
        lifetime, partitioned by species so a single instance can safely
        serve a mixed dog/cat batch (DT-1110) -- a cat crop must never be
        compared against dog reference examples. Without the cache, classifying
        a batch of N crops re-fetches and re-deserializes the entire example
        set N times -- a query per crop that dominates at scale (e.g. 30,000
        crops = 30,000 identical queries). Callers create a fresh
        IdentityClassifier per classify/reclassify run, so caching for the
        instance's lifetime does not risk missing examples added during that
        same run in practice.
        """
        if self._examples_cache is None:
            all_examples = (
                self.session.query(EmbeddingExample)
                .join(Identity)
                .where(Identity.is_active.is_(True))
                .options(contains_eager(EmbeddingExample.identity))
                .all()
            )

            self._examples_cache = {}

            for example in all_examples:
                self._examples_cache.setdefault(example.identity.species, []).append(
                    example
                )

        return self._examples_cache.get(species, [])
