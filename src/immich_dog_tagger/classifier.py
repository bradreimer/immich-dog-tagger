"""
Dog identity classifier.
"""

from collections.abc import Collection
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
    # v1.5/ADR-003: how well this example's capture date aligns with the
    # photo being classified, in [scoring.TEMPORAL_FLOOR, 1.0]. Surfaced
    # alongside the match, never folded into `similarity` (which stays a
    # raw, uncalibrated embedding score; see v1.0.0.md section 8) -- it
    # only influences which example/identity wins ranking (see
    # `weighted_score`), not the reported confidence number.
    temporal_weight: float = 1.0

    @property
    def weighted_score(self) -> float:
        return self.similarity * self.temporal_weight


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
        excluded_identities: Collection[str] | None = None,
    ) -> ClassificationResult:
        """
        `excluded_identities` are identities a human has rejected for this
        particular crop (issue #144). They are dropped before scoring, so a
        rejected pet cannot come back as the accepted identity *or* as a
        runner-up candidate on any later pass -- which is what makes a
        rejection survive Reclassify. The suppression lives here, in the one
        module that owns the nearest-neighbour decision, rather than being
        re-implemented by each caller or filtered out downstream in the
        review query.
        """
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )
        candidate_limit = (
            candidate_limit
            if candidate_limit is not None
            else self.policy.candidate_limit
        )

        excluded = frozenset(excluded_identities or ())

        identity_scores: dict[str, ClassificationCandidate] = {}

        for example in self._load_examples(species):
            if example.identity.name in excluded:
                continue

            known = blob_to_embedding(example.embedding)

            similarity = self._cosine_similarity(
                embedding,
                known,
            )

            score = self.scorer.score(
                similarity,
                query_captured_at=captured_at,
                example_captured_at=example.captured_at,
            )

            candidate = ClassificationCandidate(
                identity=example.identity.name,
                similarity=score.similarity,
                matched_example_id=example.id,
                temporal_weight=score.temporal_weight,
            )

            existing = identity_scores.get(candidate.identity)

            if existing is None or candidate.weighted_score > existing.weighted_score:
                identity_scores[candidate.identity] = candidate

        candidates = list(identity_scores.values())

        candidates.sort(
            key=lambda candidate: candidate.weighted_score,
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
