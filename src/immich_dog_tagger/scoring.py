"""
Classification scoring utilities.
"""

import math
from dataclasses import dataclass
from datetime import datetime

# Automatic temporal-recency weighting (v1.5, ADR-003): an example captured
# close in time to the photo being classified is trusted more than one from
# a very different era of the same identity's life. This is what lets a
# newly arrived, visually similar identity win over one whose examples all
# predate it (e.g. a pet that has passed away) without any owner-configured
# date range. Weighting is anchored to the photo's own capture date, not
# wall-clock "now", so classifying an old photo still favors examples from
# that same period. SIGMA_DAYS sets the ~1 year characteristic scale; FLOOR
# ensures a lone identity with only distant-in-time examples and no
# closer-in-time competitor still classifies correctly, rather than being
# driven toward zero.
TEMPORAL_SIGMA_DAYS = 365.0
TEMPORAL_FLOOR = 0.15


def temporal_weight(
    query_captured_at: datetime | None,
    example_captured_at: datetime | None,
) -> float:
    """
    Fail-open by design (matching DT-1114's date_conflict precedent): a
    missing capture date on either side returns 1.0 -- absence of date
    evidence must never penalize a match. Otherwise decays from 1.0 toward
    TEMPORAL_FLOOR as the gap between the two dates grows.
    """
    if query_captured_at is None or example_captured_at is None:
        return 1.0

    delta_days = (
        abs((query_captured_at - example_captured_at).total_seconds()) / 86400.0
    )

    decay = math.exp(-0.5 * (delta_days / TEMPORAL_SIGMA_DAYS) ** 2)

    return TEMPORAL_FLOOR + (1.0 - TEMPORAL_FLOOR) * decay


@dataclass(frozen=True)
class MatchScore:
    similarity: float
    temporal_weight: float = 1.0

    @property
    def weighted_score(self) -> float:
        return self.similarity * self.temporal_weight


class SimilarityScorer:
    """
    Calculates the quality of a match between an embedding and a known
    example: a raw cosine similarity, plus how well the example's capture
    date aligns with the photo being classified.
    """

    def score(
        self,
        similarity: float,
        *,
        query_captured_at: datetime | None = None,
        example_captured_at: datetime | None = None,
    ) -> MatchScore:
        return MatchScore(
            similarity=similarity,
            temporal_weight=temporal_weight(
                query_captured_at,
                example_captured_at,
            ),
        )
