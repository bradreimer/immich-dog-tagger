"""
Agglomerative clustering over cosine distance.

This module groups embeddings; it never decides identity. Nothing here
reads or writes a classification, a confidence, or a threshold from
`policy.py` -- clustering proposes groupings for a human to approve, and
the distance cut below is a grouping knob, not a classification boundary
(issue #141).

Average linkage is used because it is the linkage least sensitive to a
single outlying crop: single linkage chains two visually different groups
together through one intermediate photo (which is exactly how an impure
cluster gets approved in one click), and complete linkage over-splits a
pose-varied pet. Ties are broken by lowest index so the same input always
produces the same grouping -- the owner must not see a pool regroup itself
between two page loads.
"""

import numpy as np

# Cosine-distance cut: two groups merge only while their average pairwise
# distance stays at or below this. 0.20 means "at least 0.80 cosine
# similarity on average" -- deliberately the same numeric neighbourhood the
# app already treats as visually the same animal, so the grouping matches
# the owner's intuition, but owned here rather than by policy.py because it
# answers a different question ("do these photos look alike enough to show
# as one group?", not "is this the pet?").
#
# The cut is biased toward small, pure clusters: an impure cluster writes
# bad ground truth for every member at one click, while an over-split pool
# only costs the owner an extra click. Raise it for fewer, larger groups.
DEFAULT_CLUSTER_DISTANCE = 0.20


def cosine_distances(embeddings: np.ndarray) -> np.ndarray:
    """
    Pairwise cosine distances (1 - cosine similarity), clipped to [0, 2].

    A zero-norm vector is left as zeros, which puts it at distance 1.0 from
    everything -- beyond any sane cut, so it lands in its own cluster
    instead of raising or silently attaching itself to a group.
    """
    matrix = np.asarray(embeddings, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError("embeddings must be a 2-D array")

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized = np.divide(
        matrix,
        norms,
        out=np.zeros_like(matrix),
        where=norms > 0,
    )

    return np.clip(1.0 - normalized @ normalized.T, 0.0, 2.0)


def agglomerative_clusters(
    embeddings: np.ndarray,
    *,
    distance_threshold: float = DEFAULT_CLUSTER_DISTANCE,
) -> list[list[int]]:
    """
    Group row indices of `embeddings` by average-linkage agglomerative
    clustering, merging while the closest pair of groups is within
    `distance_threshold`.

    Returns clusters ordered largest first, ties broken by lowest member
    index; members within a cluster are ascending. Deterministic for
    identical input.
    """
    matrix = np.asarray(embeddings, dtype=np.float64)
    count = len(matrix)

    if count == 0:
        return []

    if count == 1:
        return [[0]]

    distances = cosine_distances(matrix)
    np.fill_diagonal(distances, np.inf)

    members: list[list[int]] = [[index] for index in range(count)]
    sizes = np.ones(count, dtype=np.float64)
    active = np.ones(count, dtype=bool)

    while active.sum() > 1:
        # Inactive rows/columns are already np.inf, so a plain argmin over
        # the whole matrix finds the closest live pair -- and returns the
        # first occurrence in row-major order, which is the lowest (i, j).
        flat = int(np.argmin(distances))
        left, right = divmod(flat, count)

        if distances[left, right] > distance_threshold:
            break

        if left > right:
            left, right = right, left

        merged_size = sizes[left] + sizes[right]

        # Lance-Williams update for average linkage: the distance from the
        # merged group to every other group is the size-weighted mean of the
        # two originals' distances.
        updated = (
            sizes[left] * distances[left] + sizes[right] * distances[right]
        ) / merged_size

        distances[left] = updated
        distances[:, left] = updated
        distances[left, left] = np.inf

        distances[right] = np.inf
        distances[:, right] = np.inf

        members[left] = sorted(members[left] + members[right])
        members[right] = []
        sizes[left] = merged_size
        active[right] = False

    clusters = [group for group in members if group]

    return sorted(clusters, key=lambda group: (-len(group), group[0]))


def medoid(embeddings: np.ndarray, indices: list[int]) -> int:
    """
    The most representative member of a group: the one with the smallest
    total cosine distance to the rest. Ties go to the lowest index, so the
    representative is stable across runs.
    """
    if not indices:
        raise ValueError("indices must not be empty")

    if len(indices) == 1:
        return indices[0]

    subset = np.asarray(embeddings, dtype=np.float64)[indices]
    totals = cosine_distances(subset).sum(axis=1)

    return indices[int(np.argmin(totals))]
