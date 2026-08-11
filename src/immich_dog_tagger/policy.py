"""
Centralized nearest-neighbor classification decision policy.

This module is the single place that owns similarity thresholds,
candidate-list size, and the confident/needs-review/unknown decision
boundary. It is used by IdentityClassifier at classification time, by
ReclassifyService at reclassification time, and by ReviewQueryService when
deciding why an item belongs in the review queue -- no other module should
implement its own threshold literal.
"""

from dataclasses import dataclass
from enum import StrEnum


class ClassificationDecision(StrEnum):
    CONFIDENT = "confident"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifierPolicy:
    """
    Deterministic, versioned classification policy.

    `version` is persisted alongside classification results so a stored
    prediction can always be traced back to the configuration that produced
    it (see CropClassification.classifier_version).
    """

    version: str = "v1"
    confident_threshold: float = 0.80
    candidate_limit: int = 3

    def decide(
        self,
        *,
        identity: str | None,
        similarity: float,
    ) -> ClassificationDecision:
        if identity is None:
            return ClassificationDecision.UNKNOWN

        if similarity < self.confident_threshold:
            return ClassificationDecision.NEEDS_REVIEW

        return ClassificationDecision.CONFIDENT


DEFAULT_POLICY = ClassifierPolicy()
