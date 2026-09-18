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
from immich_dog_tagger.services.review_groups import (
    MIN_GROUP_SIZE,
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


def test_sort_is_echoed_back(engine):
    with Session(engine) as session:
        _identity(session)

        _classification(session, path="a.jpg", embedding=[1.0, 0.0, 0.0])
        _classification(session, path="b.jpg", embedding=[0.99, 0.05, 0.0])

        proposal = ReviewGroupingService(session).groups(sort=ClusterSort.CAPTURED_ASC)

        assert proposal.sort == ClusterSort.CAPTURED_ASC
