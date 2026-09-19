"""
Service coverage for queue-wide review grouping (docs/specs/
review-tab-batch-approval.md): clustering the active review queue across
every identity with pending work, not one identity selected up front.
"""

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClusterSort, ReviewActions, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.clusters import RecommendationClusterService
from immich_dog_tagger.services.review_groups import (
    MIN_GROUP_SIZE,
    GroupMismatch,
    ReviewGroupingService,
)


def _identity(session, name="Fibs", species=Species.DOG) -> Identity:
    identity = Identity(name=name, species=species)
    session.add(identity)
    session.flush()

    return identity


def _classification(
    session,
    *,
    path: str,
    identity: str | None = "Fibs",
    confidence: float = 0.75,
    species: Species = Species.DOG,
    embedding: list[float] | None = (1.0, 0.0, 0.0),
    candidates: list[dict] | None = None,
    reviewed: bool = False,
) -> CropClassification:
    asset = Asset(immich_asset_id=f"asset-{path}", extension=".jpg")
    detection = Detection(
        asset=asset,
        label=species.value,
        confidence=0.9,
        x1=0,
        y1=0,
        x2=1,
        y2=1,
    )
    crop = Crop(detection=detection, path=path, species=species)

    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=identity,
        confidence=confidence,
        candidates=candidates or [],
        embedding=(
            embedding_to_blob(np.array(embedding, dtype=np.float32))
            if embedding is not None
            else None
        ),
    )

    session.add(classification)
    session.flush()

    if reviewed:
        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                identity=identity,
            )
        )

    session.commit()

    return classification


def test_groups_span_every_identity_with_pending_work(engine):
    with Session(engine) as session:
        _identity(session, "Fibs")
        _identity(session, "Rex")

        _classification(
            session, path="fibs-a.jpg", identity="Fibs", embedding=[1.0, 0.0, 0.0]
        )
        _classification(
            session, path="fibs-b.jpg", identity="Fibs", embedding=[0.99, 0.05, 0.0]
        )

        _classification(
            session, path="rex-a.jpg", identity="Rex", embedding=[0.0, 1.0, 0.0]
        )
        _classification(
            session, path="rex-b.jpg", identity="Rex", embedding=[0.0, 0.99, 0.05]
        )

        proposal = ReviewGroupingService(session).groups()

        assert proposal.identity_count == 2
        assert proposal.truncated_identities is False
        assert {group.identity for group in proposal.groups} == {"Fibs", "Rex"}
        assert all(group.cluster.size == 2 for group in proposal.groups)


def test_singleton_clusters_are_excluded(engine):
    """A lone pending photo has no batching benefit over Queue mode."""
    with Session(engine) as session:
        _identity(session)

        _classification(session, path="a.jpg", embedding=[1.0, 0.0, 0.0])
        _classification(session, path="b.jpg", embedding=[0.0, 1.0, 0.0])

        proposal = ReviewGroupingService(session).groups()

        assert proposal.groups == []
        assert MIN_GROUP_SIZE == 2


def test_candidate_only_identity_is_grouped(engine):
    """An identity that only ever appears as a runner-up candidate still
    gets its own group, not just the accepted identity."""
    with Session(engine) as session:
        _identity(session, "Fibs")
        _identity(session, "Rex")

        candidates = [{"identity": "Rex", "similarity": 0.8}]

        _classification(
            session,
            path="a.jpg",
            identity="Fibs",
            candidates=candidates,
            embedding=[1.0, 0.0, 0.0],
        )
        _classification(
            session,
            path="b.jpg",
            identity="Fibs",
            candidates=candidates,
            embedding=[0.99, 0.05, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        identities = {group.identity for group in proposal.groups}
        assert identities == {"Fibs", "Rex"}


def test_reviewed_classifications_are_excluded(engine):
    with Session(engine) as session:
        _identity(session)

        _classification(session, path="a.jpg", embedding=[1.0, 0.0, 0.0], reviewed=True)
        _classification(
            session, path="b.jpg", embedding=[0.99, 0.05, 0.0], reviewed=True
        )

        proposal = ReviewGroupingService(session).groups()

        assert proposal.groups == []
        assert proposal.identity_count == 0


def test_confidently_classified_unreviewed_items_are_excluded(engine):
    """
    Issue #341: a classification with confidence at or above the policy's
    `confident_threshold` but no `ReviewAction` yet doesn't need a human
    decision -- Queue mode's `active_review()` already excludes it, so
    Grouped mode must not pool or cluster it either, or the reviewer sees
    the same "confident" photos resurface group after group with no way to
    clear them short of an explicit approval they were never asked for.
    """
    with Session(engine) as session:
        _identity(session, "Fibs")

        _classification(
            session,
            path="confident-a.jpg",
            identity="Fibs",
            confidence=0.95,
            embedding=[1.0, 0.0, 0.0],
        )
        _classification(
            session,
            path="confident-b.jpg",
            identity="Fibs",
            confidence=0.9,
            embedding=[0.99, 0.05, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        assert proposal.groups == []
        assert proposal.identity_count == 0


def test_mixed_confidence_group_keeps_only_items_needing_review(engine):
    with Session(engine) as session:
        _identity(session, "Fibs")

        confident = _classification(
            session,
            path="confident.jpg",
            identity="Fibs",
            confidence=0.95,
            embedding=[1.0, 0.0, 0.0],
        )
        needs_review_a = _classification(
            session,
            path="needs-review-a.jpg",
            identity="Fibs",
            confidence=0.5,
            embedding=[0.99, 0.05, 0.0],
        )
        needs_review_b = _classification(
            session,
            path="needs-review-b.jpg",
            identity="Fibs",
            confidence=0.6,
            embedding=[0.98, 0.06, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        assert len(proposal.groups) == 1
        member_ids = {
            member.classification_id for member in proposal.groups[0].cluster.members
        }
        assert member_ids == {needs_review_a.id, needs_review_b.id}
        assert confident.id not in member_ids


def test_groups_sorted_by_size_descending(engine):
    with Session(engine) as session:
        _identity(session, "Fibs")
        _identity(session, "Rex")

        # Fibs: a cluster of two.
        _classification(
            session, path="fibs-a.jpg", identity="Fibs", embedding=[1.0, 0.0, 0.0]
        )
        _classification(
            session, path="fibs-b.jpg", identity="Fibs", embedding=[0.99, 0.05, 0.0]
        )

        # Rex: a cluster of three.
        _classification(
            session, path="rex-a.jpg", identity="Rex", embedding=[0.0, 1.0, 0.0]
        )
        _classification(
            session, path="rex-b.jpg", identity="Rex", embedding=[0.0, 0.99, 0.05]
        )
        _classification(
            session, path="rex-c.jpg", identity="Rex", embedding=[0.0, 0.98, 0.06]
        )

        proposal = ReviewGroupingService(session).groups()

        assert [group.cluster.size for group in proposal.groups] == [3, 2]
        assert proposal.groups[0].identity == "Rex"


def test_max_identities_caps_the_scan(engine):
    with Session(engine) as session:
        for index in range(3):
            name = f"Pet{index}"
            _identity(session, name)
            _classification(
                session, path=f"{name}-a.jpg", identity=name, embedding=[1.0, 0.0, 0.0]
            )
            _classification(
                session,
                path=f"{name}-b.jpg",
                identity=name,
                embedding=[0.99, 0.05, 0.0],
            )

        proposal = ReviewGroupingService(session, max_identities=2).groups()

        assert proposal.identity_count == 2
        assert proposal.truncated_identities is True
        assert len({group.identity for group in proposal.groups}) <= 2


def test_pending_pool_is_scanned_once_per_species_not_per_identity(engine, monkeypatch):
    """
    Issue #333: before this, `groups()` called `clusters()` once per
    identity with pending work, and each of those calls re-ran its own
    full-species scan of the pending pool -- for a library with a few
    thousand pending candidates, that turned "load the grouped Review tab"
    into a query cost that grew with the number of identities rather than
    staying flat. `groups()` now fetches the pool once per distinct species
    via `pending_pool()` and slices it per identity with `clusters_in_pool()`
    -- pinned here by spying on `pending_pool()` itself rather than a raw
    SQL query count, so the assertion survives unrelated query-shape changes
    elsewhere in the read path.
    """
    calls = []
    original = RecommendationClusterService.pending_pool

    def spy(self, species):
        calls.append(species)
        return original(self, species)

    monkeypatch.setattr(RecommendationClusterService, "pending_pool", spy)

    with Session(engine) as session:
        for index in range(4):
            name = f"Pet{index}"
            _identity(session, name)
            _classification(
                session, path=f"{name}-a.jpg", identity=name, embedding=[1.0, 0.0, 0.0]
            )
            _classification(
                session,
                path=f"{name}-b.jpg",
                identity=name,
                embedding=[0.99, 0.05, 0.0],
            )

        proposal = ReviewGroupingService(session).groups()

        assert proposal.identity_count == 4
        assert calls == [Species.DOG]


def test_sort_is_echoed_back(engine):
    with Session(engine) as session:
        _identity(session)

        _classification(session, path="a.jpg", embedding=[1.0, 0.0, 0.0])
        _classification(session, path="b.jpg", embedding=[0.99, 0.05, 0.0])

        proposal = ReviewGroupingService(session).groups(sort=ClusterSort.CAPTURED_ASC)

        assert proposal.sort == ClusterSort.CAPTURED_ASC


# docs/specs/review-groups-temporal-spatial-refinement.md: a member is only
# unflagged when the group's identity is its own top-ranked
# (weighted-by-time-and-location) prediction -- candidates[0], since
# candidates is stored sorted by weighted_score = similarity *
# temporal_weight * spatial_weight (classifier.py). These tests build that
# invariant by hand rather than through the classifier, so each scenario
# controls exactly which candidate is "top" and why.


def test_member_agreeing_with_group_identity_is_unflagged(engine):
    with Session(engine) as session:
        _identity(session, "Fibs")

        _classification(
            session,
            path="a.jpg",
            identity="Fibs",
            candidates=[{"identity": "Fibs", "similarity": 0.9}],
            embedding=[1.0, 0.0, 0.0],
        )
        _classification(
            session,
            path="b.jpg",
            identity="Fibs",
            candidates=[{"identity": "Fibs", "similarity": 0.85}],
            embedding=[0.99, 0.05, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        assert len(proposal.groups) == 1
        assert proposal.groups[0].mismatches == []


def test_member_with_weak_temporal_weight_is_flagged(engine):
    with Session(engine) as session:
        _identity(session, "Fibs")
        _identity(session, "Rex")

        mismatched = _classification(
            session,
            path="a.jpg",
            identity=None,
            candidates=[
                {"identity": "Rex", "similarity": 0.9},
                {"identity": "Fibs", "similarity": 0.85, "temporal_weight": 0.2},
            ],
            embedding=[1.0, 0.0, 0.0],
        )
        _classification(
            session,
            path="b.jpg",
            identity="Fibs",
            candidates=[{"identity": "Fibs", "similarity": 0.85}],
            embedding=[0.99, 0.05, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        fibs_group = next(g for g in proposal.groups if g.identity == "Fibs")

        assert fibs_group.mismatches == [
            GroupMismatch(classification_id=mismatched.id, reason="temporal-mismatch")
        ]


def test_member_with_weak_spatial_weight_is_flagged(engine):
    with Session(engine) as session:
        _identity(session, "Fibs")
        _identity(session, "Rex")

        mismatched = _classification(
            session,
            path="a.jpg",
            identity=None,
            candidates=[
                {"identity": "Rex", "similarity": 0.9},
                {"identity": "Fibs", "similarity": 0.85, "spatial_weight": 0.1},
            ],
            embedding=[1.0, 0.0, 0.0],
        )
        _classification(
            session,
            path="b.jpg",
            identity="Fibs",
            candidates=[{"identity": "Fibs", "similarity": 0.85}],
            embedding=[0.99, 0.05, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        fibs_group = next(g for g in proposal.groups if g.identity == "Fibs")

        assert fibs_group.mismatches == [
            GroupMismatch(classification_id=mismatched.id, reason="location-mismatch")
        ]


def test_member_losing_on_visual_similarity_alone_gets_generic_reason(engine):
    """Neither temporal nor spatial weight explains the mismatch (both are
    the fail-open default of 1.0, i.e. missing capture date/location) -- the
    member simply lost the ranking on raw similarity, so it's labeled with
    the generic reason rather than a temporal/spatial one it didn't earn."""
    with Session(engine) as session:
        _identity(session, "Fibs")
        _identity(session, "Rex")

        mismatched = _classification(
            session,
            path="a.jpg",
            identity=None,
            candidates=[
                {"identity": "Rex", "similarity": 0.95},
                {"identity": "Fibs", "similarity": 0.8},
            ],
            embedding=[1.0, 0.0, 0.0],
        )
        _classification(
            session,
            path="b.jpg",
            identity="Fibs",
            candidates=[{"identity": "Fibs", "similarity": 0.85}],
            embedding=[0.99, 0.05, 0.0],
        )

        proposal = ReviewGroupingService(session).groups()

        fibs_group = next(g for g in proposal.groups if g.identity == "Fibs")

        assert fibs_group.mismatches == [
            GroupMismatch(
                classification_id=mismatched.id, reason="different-top-prediction"
            )
        ]
