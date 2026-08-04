"""
Classification scoring utilities.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchScore:
    similarity: float


class SimilarityScorer:
    """
    Calculates the quality of a match between an embedding
    and a known example.
    """

    def score(
        self,
        similarity: float,
    ) -> MatchScore:
        return MatchScore(
            similarity=similarity,
        )
