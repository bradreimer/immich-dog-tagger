from datetime import UTC, datetime

import pytest

from immich_dog_tagger.scoring import (
    TEMPORAL_FLOOR,
    SimilarityScorer,
    temporal_weight,
)


def _dt(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_temporal_weight_is_one_for_coincident_dates():
    same = _dt(2024, 3, 1)

    assert temporal_weight(same, same) == pytest.approx(1.0)


def test_temporal_weight_decays_as_the_gap_grows():
    query = _dt(2024, 1, 1)
    one_year_away = _dt(2023, 1, 1)
    two_years_away = _dt(2022, 1, 1)

    weight_one_year = temporal_weight(query, one_year_away)
    weight_two_years = temporal_weight(query, two_years_away)

    assert weight_one_year < 1.0
    assert weight_two_years < weight_one_year


def test_temporal_weight_never_drops_below_the_floor():
    query = _dt(2024, 1, 1)
    decades_away = _dt(1990, 1, 1)

    weight = temporal_weight(query, decades_away)

    assert weight >= TEMPORAL_FLOOR
    assert weight == pytest.approx(TEMPORAL_FLOOR, abs=1e-6)


def test_temporal_weight_is_symmetric():
    a = _dt(2024, 1, 1)
    b = _dt(2023, 6, 1)

    assert temporal_weight(a, b) == pytest.approx(temporal_weight(b, a))


@pytest.mark.parametrize(
    ("query_captured_at", "example_captured_at"),
    [
        (None, _dt(2020, 1, 1)),
        (_dt(2020, 1, 1), None),
        (None, None),
    ],
)
def test_temporal_weight_fails_open_when_a_date_is_missing(
    query_captured_at, example_captured_at
):
    assert temporal_weight(query_captured_at, example_captured_at) == 1.0


def test_similarity_scorer_reports_raw_similarity_and_temporal_weight():
    scorer = SimilarityScorer()
    same_date = _dt(2024, 1, 1)

    score = scorer.score(
        0.87,
        query_captured_at=same_date,
        example_captured_at=same_date,
    )

    assert score.similarity == 0.87
    assert score.temporal_weight == pytest.approx(1.0)
    assert score.weighted_score == pytest.approx(0.87)


def test_similarity_scorer_defaults_to_full_weight_without_dates():
    scorer = SimilarityScorer()

    score = scorer.score(0.75)

    assert score.similarity == 0.75
    assert score.temporal_weight == 1.0
    assert score.weighted_score == 0.75
