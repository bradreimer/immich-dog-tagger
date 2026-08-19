"""
Service coverage for cluster recommendations and cluster approval
(issue #141).
"""

from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    PetOccurrence,
    ReviewAction,
)
from immich_dog_tagger.services.clusters import (
    ClusterApprovalService,
    RecommendationClusterService,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.learner import Learner


class FakeEmbedder:
    """Every crop path embeds to a fixed vector, so learning is deterministic."""

    def __init__(self, vector=(1.0, 0.0, 0.0)):
        self.vector = np.array(vector, dtype=np.float32)
        self.calls = 0

    def embed(self, path):
        self.calls += 1
        return self.vector


class ExplodingEmbedder(FakeEmbedder):
    """Fails once a given number of crops have been learned."""

    def __init__(self, fail_after: int):
        super().__init__()
        self.fail_after = fail_after

    def embed(self, path):
        if self.calls >= self.fail_after:
            raise RuntimeError("embedder exploded")

        return super().embed(path)


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
    captured_at: datetime | None = None,
    reviewed: bool = False,
) -> CropClassification:
    asset = Asset(
        immich_asset_id=f"asset-{path}",
        extension=".jpg",
        captured_at=captured_at,
    )
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


def _approval_service(session, embedder=None) -> ClusterApprovalService:
    correction = ClassificationCorrectionService(
        session=session,
        learner=Learner(embedder=embedder or FakeEmbedder(), session=session),
    )

    return ClusterApprovalService(session, correction)


def test_clusters_group_similar_crops_and_separate_dissimilar_ones(engine):
    with Session(engine) as session:
        _identity(session)

        _classification(session, path="a.jpg", embedding=[1.0, 0.0, 0.0])
        _classification(session, path="b.jpg", embedding=[0.99, 0.05, 0.0])
        _classification(session, path="c.jpg", embedding=[0.0, 1.0, 0.0])

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        assert [cluster.size for cluster in proposal.clusters] == [2, 1]
        assert proposal.candidate_count == 3
        assert proposal.clustered_count == 3
        assert proposal.excluded == []
        assert proposal.truncated is False

        paths = {member.path.name for member in proposal.clusters[0].members}
        assert paths == {"a.jpg", "b.jpg"}


def test_cluster_reports_representative_counts_and_ranges(engine):
    with Session(engine) as session:
        _identity(session)

        earliest = datetime(2024, 5, 1, tzinfo=UTC)
        latest = datetime(2026, 2, 3, tzinfo=UTC)

        first = _classification(
            session,
            path="a.jpg",
            confidence=0.72,
            captured_at=earliest,
        )
        _classification(
            session,
            path="b.jpg",
            confidence=0.91,
            captured_at=latest,
        )

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        cluster = proposal.clusters[0]

        assert cluster.size == 2
        assert cluster.id == first.id
        assert cluster.representative.classification_id in {
            member.classification_id for member in cluster.members
        }
        assert cluster.min_similarity == pytest.approx(0.72)
        assert cluster.max_similarity == pytest.approx(0.91)
        # SQLite stores naive datetimes, so compare on the wall clock it kept.
        assert cluster.earliest_captured_at == earliest.replace(tzinfo=None)
        assert cluster.latest_captured_at == latest.replace(tzinfo=None)


def test_pool_includes_crops_where_the_pet_is_only_a_candidate(engine):
    with Session(engine) as session:
        _identity(session)

        _classification(
            session,
            path="runner-up.jpg",
            identity="Hermann",
            confidence=0.62,
            candidates=[
                {"identity": "Hermann", "similarity": 0.62},
                {"identity": "Fibs", "similarity": 0.58},
            ],
        )

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        assert proposal.candidate_count == 1
        # The similarity reported is Fibs' own, not the top candidate's --
        # reporting 0.62 here would overstate the case for Fibs.
        assert proposal.clusters[0].min_similarity == pytest.approx(0.58)


def test_pool_excludes_reviewed_other_species_and_unrelated_crops(engine):
    with Session(engine) as session:
        _identity(session)
        _identity(session, name="Fibs", species=Species.CAT)

        _classification(session, path="pending.jpg")
        _classification(session, path="reviewed.jpg", reviewed=True)
        _classification(session, path="cat.jpg", species=Species.CAT)
        _classification(session, path="other.jpg", identity="Hermann")
        _classification(session, path="unknown.jpg", identity=None, confidence=-1.0)

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        members = {
            member.path.name
            for cluster in proposal.clusters
            for member in cluster.members
        }

        assert members == {"pending.jpg"}


def test_clustering_writes_nothing(engine):
    with Session(engine) as session:
        _identity(session)

        _classification(session, path="a.jpg")
        _classification(session, path="b.jpg", embedding=[0.0, 1.0, 0.0])

        service = RecommendationClusterService(session)

        def snapshot():
            return {
                "classifications": session.scalars(
                    select(CropClassification.id, CropClassification.identity)
                ).all(),
                "confidences": session.scalars(
                    select(CropClassification.confidence)
                ).all(),
                "review_actions": session.scalar(
                    select(func.count()).select_from(ReviewAction)
                ),
                "examples": session.scalar(
                    select(func.count()).select_from(EmbeddingExample)
                ),
                "occurrences": session.scalar(
                    select(func.count()).select_from(PetOccurrence)
                ),
            }

        before = snapshot()

        first = service.clusters(identity="Fibs", species=Species.DOG)
        second = service.clusters(identity="Fibs", species=Species.DOG)

        assert snapshot() == before
        assert [cluster.id for cluster in first.clusters] == [
            cluster.id for cluster in second.clusters
        ]
        assert [
            [member.classification_id for member in cluster.members]
            for cluster in first.clusters
        ] == [
            [member.classification_id for member in cluster.members]
            for cluster in second.clusters
        ]


def test_crops_without_an_embedding_are_excluded_not_crashed_on(engine):
    with Session(engine) as session:
        _identity(session)

        clustered = _classification(session, path="a.jpg")
        missing = _classification(session, path="legacy.jpg", embedding=None)

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        assert proposal.candidate_count == 2
        assert proposal.clustered_count == 1
        assert proposal.clusters[0].members[0].classification_id == clustered.id
        assert [
            (excluded.classification_id, excluded.reason)
            for excluded in proposal.excluded
        ] == [(missing.id, "no-embedding")]


def test_pool_is_capped_and_reports_truncation(engine):
    with Session(engine) as session:
        _identity(session)

        for index in range(5):
            _classification(
                session,
                path=f"crop-{index}.jpg",
                confidence=0.50 + index / 100,
            )

        service = RecommendationClusterService(session, max_pool=3)

        proposal = service.clusters(identity="Fibs", species=Species.DOG)

        assert proposal.truncated is True
        assert proposal.candidate_count == 3
        # Capping keeps the strongest candidates, not an arbitrary three.
        assert proposal.clustered_count == 3
        assert {member.path.name for member in proposal.clusters[0].members} == {
            "crop-4.jpg",
            "crop-3.jpg",
            "crop-2.jpg",
        }


def test_a_pet_with_no_pending_candidates_returns_an_empty_proposal(engine):
    with Session(engine) as session:
        _identity(session)

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        assert proposal.clusters == []
        assert proposal.excluded == []
        assert proposal.candidate_count == 0
        assert proposal.truncated is False


def test_clustering_an_unknown_pet_is_an_error(engine):
    with Session(engine) as session:
        _identity(session)

        with pytest.raises(ValueError):
            RecommendationClusterService(session).clusters(
                identity="Nobody",
                species=Species.DOG,
            )

        # Names are unique per species, so the dog Fibs is not the cat Fibs.
        with pytest.raises(ValueError):
            RecommendationClusterService(session).clusters(
                identity="Fibs",
                species=Species.CAT,
            )


def test_approving_a_cluster_creates_one_correction_per_member(engine):
    with Session(engine) as session:
        _identity(session)

        members = [
            _classification(session, path=f"crop-{index}.jpg") for index in range(4)
        ]

        summary = _approval_service(session).approve(
            identity="Fibs",
            species=Species.DOG,
            classification_ids=[member.id for member in members],
        )

        assert summary.applied == 4
        assert summary.skipped == 0

        actions = session.scalars(select(ReviewAction)).all()

        assert len(actions) == 4
        assert {action.action for action in actions} == {ReviewActions.CORRECT}
        assert {action.identity for action in actions} == {"Fibs"}

        examples = session.scalars(select(EmbeddingExample)).all()

        assert len(examples) == 4
        assert {example.source for example in examples} == {EmbeddingSources.REVIEW}
        assert {example.crop_path for example in examples} == {
            f"crop-{index}.jpg" for index in range(4)
        }

        for member in members:
            session.refresh(member)

            assert member.identity == "Fibs"
            assert member.confidence == 1.0
            assert member.source == ClassificationSources.REVIEW


def test_approval_reports_what_it_skipped_and_why(engine):
    with Session(engine) as session:
        _identity(session)

        applied = _classification(session, path="applied.jpg")
        reviewed = _classification(session, path="reviewed.jpg", reviewed=True)
        cat = _classification(session, path="cat.jpg", species=Species.CAT)

        summary = _approval_service(session).approve(
            identity="Fibs",
            species=Species.DOG,
            classification_ids=[
                applied.id,
                applied.id,
                reviewed.id,
                cat.id,
                9999,
            ],
        )

        assert summary.applied == 1
        assert summary.skipped == 4
        assert {(skip.classification_id, skip.reason) for skip in summary.skips} == {
            (applied.id, "duplicate"),
            (reviewed.id, "already-reviewed"),
            (cat.id, "species-mismatch"),
            (9999, "not-found"),
        }


def test_approval_leaves_committed_progress_when_it_fails_midway(engine):
    with Session(engine) as session:
        _identity(session)

        members = [
            _classification(session, path=f"crop-{index}.jpg") for index in range(7)
        ]

        correction = ClassificationCorrectionService(
            session=session,
            learner=Learner(embedder=ExplodingEmbedder(fail_after=5), session=session),
        )
        service = ClusterApprovalService(session, correction, batch_size=2)

        with pytest.raises(RuntimeError):
            service.approve(
                identity="Fibs",
                species=Species.DOG,
                classification_ids=[member.id for member in members],
            )

    # A fresh session: only what actually reached disk counts.
    with Session(engine) as session:
        committed = session.scalar(select(func.count()).select_from(ReviewAction))

        # Four members committed in two batches of two; the fifth failed and
        # took only its own uncommitted batch down with it.
        assert committed == 4
        assert session.scalar(select(func.count()).select_from(EmbeddingExample)) == 4


def test_approval_rejects_an_unbounded_request(engine):
    with Session(engine) as session:
        _identity(session)

        service = _approval_service(session)

        with pytest.raises(ValueError):
            service.approve(
                identity="Fibs",
                species=Species.DOG,
                classification_ids=list(range(2000)),
            )


def test_approving_for_an_unknown_pet_is_an_error(engine):
    with Session(engine) as session:
        _identity(session)

        classification = _classification(session, path="a.jpg")

        with pytest.raises(ValueError):
            _approval_service(session).approve(
                identity="Nobody",
                species=Species.DOG,
                classification_ids=[classification.id],
            )

        assert session.scalar(select(func.count()).select_from(ReviewAction)) == 0


def test_approved_members_leave_the_candidate_pool(engine):
    with Session(engine) as session:
        _identity(session)

        members = [
            _classification(session, path=f"crop-{index}.jpg") for index in range(3)
        ]

        service = RecommendationClusterService(session)

        assert (
            service.clusters(identity="Fibs", species=Species.DOG).candidate_count == 3
        )

        _approval_service(session).approve(
            identity="Fibs",
            species=Species.DOG,
            classification_ids=[members[0].id, members[1].id],
        )

        after = service.clusters(identity="Fibs", species=Species.DOG)

        assert after.candidate_count == 1
        assert after.clusters[0].members[0].classification_id == members[2].id
