"""
Classification scoring utilities.
"""

from datetime import datetime


def temporal_score(
    captured_at: datetime | None,
    example_created_at: datetime | None,
) -> float:
    """
    Estimate similarity based on time proximity.

    Returns:
        1.0 for very close dates
        decreasing toward 0.0 for distant dates.
    """

    if captured_at is None or example_created_at is None:
        return 0.0

    days = abs((captured_at - example_created_at).days)

    # One year decay.
    return max(
        0.0,
        1.0 - (days / 365),
    )


def combined_score(
    visual_similarity: float,
    temporal_similarity: float,
    temporal_weight: float = 0.1,
) -> float:
    """
    Combine visual and temporal signals.
    """

    return (
        visual_similarity * (1 - temporal_weight)
        + temporal_similarity * temporal_weight
    )
