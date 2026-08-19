"""Unit coverage for the clustering primitive itself (issue #141)."""

import numpy as np
import pytest

from immich_dog_tagger.clustering import (
    agglomerative_clusters,
    cosine_distances,
    medoid,
)


def test_groups_similar_vectors_and_separates_dissimilar_ones():
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.99, 0.1, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.98, 0.05],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    assert agglomerative_clusters(vectors, distance_threshold=0.2) == [
        [0, 1],
        [2, 3],
        [4],
    ]


def test_is_deterministic_for_identical_input():
    generator = np.random.default_rng(seed=7)
    vectors = generator.normal(size=(60, 16))

    first = agglomerative_clusters(vectors, distance_threshold=0.35)
    second = agglomerative_clusters(vectors, distance_threshold=0.35)

    assert first == second


def test_threshold_controls_how_much_merges():
    vectors = np.array(
        [
            [1.0, 0.0],
            [0.9, 0.44],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )

    tight = agglomerative_clusters(vectors, distance_threshold=0.01)
    loose = agglomerative_clusters(vectors, distance_threshold=1.0)

    assert tight == [[0], [1], [2]]
    assert loose == [[0, 1, 2]]


def test_empty_and_single_inputs():
    assert agglomerative_clusters(np.zeros((0, 3))) == []
    assert agglomerative_clusters(np.zeros((1, 3))) == [[0]]


def test_zero_vector_never_joins_a_cluster():
    vectors = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 0.0],
        ],
        dtype=np.float32,
    )

    assert agglomerative_clusters(vectors, distance_threshold=0.2) == [[0, 1], [2]]


def test_clusters_are_ordered_largest_first():
    vectors = np.array(
        [
            [0.0, 1.0],
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
        ],
        dtype=np.float32,
    )

    assert agglomerative_clusters(vectors, distance_threshold=0.05) == [[1, 2, 3], [0]]


def test_cosine_distances_are_symmetric_and_bounded():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]], dtype=np.float32)

    distances = cosine_distances(vectors)

    assert np.allclose(distances, distances.T)
    assert distances.min() >= 0.0
    assert distances.max() <= 2.0
    assert distances[0, 0] == pytest.approx(0.0)
    assert distances[0, 2] == pytest.approx(2.0)


def test_medoid_picks_the_most_central_member():
    vectors = np.array(
        [
            [1.0, 0.0],
            [0.92, 0.39],
            [0.71, 0.71],
        ],
        dtype=np.float32,
    )

    assert medoid(vectors, [0, 1, 2]) == 1
    assert medoid(vectors, [2]) == 2


def test_medoid_requires_members():
    with pytest.raises(ValueError):
        medoid(np.zeros((2, 2)), [])
