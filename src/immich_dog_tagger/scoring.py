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

# Automatic spatial-proximity weighting (v1.9, ADR-007): the same idea as
# temporal weighting, applied to where a photo was taken rather than when.
# Two visually similar dogs/cats are often photographed in different
# characteristic places (different homes, different regular walk routes),
# so an example taken near the photo being classified is trusted more than
# one taken far away. SIGMA_KM sets a dog's usual neighborhood/walking-route
# radius as the characteristic scale; FLOOR ensures a lone identity with
# only far-away examples and no closer competitor still classifies
# correctly, rather than being driven toward zero.
SPATIAL_SIGMA_KM = 2.0
SPATIAL_FLOOR = 0.15

_EARTH_RADIUS_KM = 6371.0


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


def _haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def spatial_weight(
    query_latitude: float | None,
    query_longitude: float | None,
    example_latitude: float | None,
    example_longitude: float | None,
) -> float:
    """
    Fail-open by design, matching temporal_weight: a missing coordinate on
    either side returns 1.0 -- absence of location evidence must never
    penalize a match. Otherwise decays from 1.0 toward SPATIAL_FLOOR as the
    great-circle distance between the two points grows.
    """
    if (
        query_latitude is None
        or query_longitude is None
        or example_latitude is None
        or example_longitude is None
    ):
        return 1.0

    distance_km = _haversine_km(
        query_latitude,
        query_longitude,
        example_latitude,
        example_longitude,
    )

    decay = math.exp(-0.5 * (distance_km / SPATIAL_SIGMA_KM) ** 2)

    return SPATIAL_FLOOR + (1.0 - SPATIAL_FLOOR) * decay


@dataclass(frozen=True)
class MatchScore:
    similarity: float
    temporal_weight: float = 1.0
    spatial_weight: float = 1.0

    @property
    def weighted_score(self) -> float:
        return self.similarity * self.temporal_weight * self.spatial_weight


class SimilarityScorer:
    """
    Calculates the quality of a match between an embedding and a known
    example: a raw cosine similarity, plus how well the example's capture
    date and location align with the photo being classified.
    """

    def score(
        self,
        similarity: float,
        *,
        query_captured_at: datetime | None = None,
        example_captured_at: datetime | None = None,
        query_latitude: float | None = None,
        query_longitude: float | None = None,
        example_latitude: float | None = None,
        example_longitude: float | None = None,
    ) -> MatchScore:
        return MatchScore(
            similarity=similarity,
            temporal_weight=temporal_weight(
                query_captured_at,
                example_captured_at,
            ),
            spatial_weight=spatial_weight(
                query_latitude,
                query_longitude,
                example_latitude,
                example_longitude,
            ),
        )
