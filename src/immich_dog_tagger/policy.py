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

from immich_dog_tagger.enums import TaggingSensitivity


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


# The owner-facing sensitivity settings (issue #149), as thresholds.
#
# This table is the whole mechanism: sensitivity has exactly one effect,
# and it happens here, so the v1.0.0 rule that one module owns the
# confident/needs-review/unknown boundary still holds. Nothing else in the
# codebase may hold a threshold literal.
#
# The values sit either side of the long-standing 0.80 default rather than
# spanning the full range: this changes how much review the owner is asked
# for, not what the confidence number means, and a setting that let
# automatic tagging run at 0.5 similarity would quietly turn a
# nearest-neighbour score into a claim it cannot support.
SENSITIVITY_THRESHOLDS: dict[TaggingSensitivity, float] = {
    TaggingSensitivity.CAUTIOUS: 0.86,
    TaggingSensitivity.BALANCED: 0.80,
    TaggingSensitivity.EAGER: 0.74,
}

DEFAULT_SENSITIVITY = TaggingSensitivity.BALANCED


def policy_for(sensitivity: TaggingSensitivity) -> ClassifierPolicy:
    """
    The policy for an owner-chosen sensitivity.

    The version string stays "v1" at the default so existing rows keep
    meaning what they meant, and carries the setting otherwise -- a
    prediction produced under a non-default sensitivity has to be traceable
    back to it, which is the guarantee `classifier_version` exists for.
    """
    version = "v1" if sensitivity is DEFAULT_SENSITIVITY else f"v1-{sensitivity.value}"

    return ClassifierPolicy(
        version=version,
        confident_threshold=SENSITIVITY_THRESHOLDS[sensitivity],
    )


DEFAULT_POLICY = ClassifierPolicy()
