"""
DT-1009: end-to-end regression coverage for the critical user journey --

    fresh project -> pipeline -> review -> reclassify -> repeat

This exercises the real services together (ClassificationService,
ClassificationCorrectionService, Learner, ReclassifyService, the job
runner, and database migration) rather than each in isolation, so it
catches the cross-service regressions that unit tests miss.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationMode,
    ClassificationSources,
    EmbeddingSources,
    PipelineOperation,
    Species,
)
from immich_dog_tagger.models import (
    Asset,
    ClassificationPass,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.services.clusters import (
    ClusterApprovalService,
    RecommendationClusterService,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.reclassify import ReclassifyService
from immich_dog_tagger.services.sync import SyncService
from immich_dog_tagger.services.sync_policy import SyncPolicy


class FakeVectorEmbedder:
    """Deterministic embedder: every path maps to a known, fixed vector."""

    def __init__(self, path_to_vector: dict[str, list[float]]):
        self.path_to_vector = path_to_vector

    def embed(self, path):
        return np.array(self.path_to_vector[str(path)], dtype=np.float32)

    def embed_batch(self, paths):
        return np.array(
            [self.path_to_vector[str(path)] for path in paths], dtype=np.float32
        )


def test_full_review_driven_learning_loop(engine):
    with Session(engine) as session:
        # --- Scenario 1 & 12: fresh project, zero labels, zero examples ---
        assert session.query(Identity).count() == 0
        assert session.query(EmbeddingExample).count() == 0

        path_to_vector: dict[str, list[float]] = {}
        crops: list[tuple[Crop, str]] = []

        def add_crop(label: str, index: int, vector: list[float]) -> Crop:
            path = f"{label}-{index}.jpg"
            path_to_vector[path] = vector
            crop = Crop(detection_id=1, path=path)
            session.add(crop)
            session.flush()
            crops.append((crop, path))
            return crop

        # 15 crops that look like "Fibs", 15 that look like "Hermann", 10
        # ambiguous crops that should never confidently match anyone.
        for i in range(15):
            add_crop("fibs", i, [1.0, 0.0, 0.0])
        for i in range(15):
            add_crop("hermann", i, [0.0, 1.0, 0.0])
        for i in range(10):
            add_crop("ambiguous", i, [0.5, 0.5, 0.0])

        session.commit()

        embedder = FakeVectorEmbedder(path_to_vector)

        # --- Scenario 2: initial pipeline classify pass ---
        classification_service = ClassificationService(
            session, embedder, IdentityClassifier(session)
        )
        summary = classification_service.classify(mode=ClassificationMode.PENDING)

        assert summary.classified == 40
        # Scenario 13/14: zero examples -> everything is Unknown, nothing
        # confidently or incorrectly labeled.
        assert summary.identities == {"Unknown": 40}

        # --- Scenario 13: a legacy row with no cached embedding (as if it
        # predates the embedding-cache migration) must still be reclassifiable. ---
        legacy_crop = add_crop("fibs", 99, [1.0, 0.0, 0.0])
        session.add(
            CropClassification(
                crop=legacy_crop,
                identity=None,
                confidence=-1.0,
                source=ClassificationSources.AUTO,
                embedding=None,
            )
        )
        session.commit()

        # --- Scenario 3 & 4: review a batch of items (30 here; the same
        # code path the product recommends running at 50-100 scale). ---
        learner = Learner(embedder, session)
        correction = ClassificationCorrectionService(session, learner)

        reviewed_fibs_ids = []
        reviewed_hermann_ids = []

        for crop, _path in crops[:15]:
            classification_id = crop.classification.id
            correction.correct(classification_id, "Fibs")
            reviewed_fibs_ids.append(classification_id)

        for crop, _path in crops[15:25]:
            classification_id = crop.classification.id
            correction.correct(classification_id, "Hermann")
            reviewed_hermann_ids.append(classification_id)

        # DT-1003 acceptance: N reviewed images -> N labeled examples, no
        # duplication or leakage.
        assert session.query(EmbeddingExample).count() == 25

        # --- Scenario 5: Reclassify ---
        reclassify_service = ReclassifyService(session, embedder)
        first_pass = reclassify_service.reclassify()

        assert first_pass.eligible_count == 16  # 40 - 25 reviewed + 1 legacy
        assert first_pass.changed_count > 0

        # --- Scenario 6: reviewed labels are completely unchanged ---
        for classification_id in reviewed_fibs_ids:
            classification = session.get(CropClassification, classification_id)
            assert classification.identity == "Fibs"
            assert classification.source == ClassificationSources.REVIEW

        for classification_id in reviewed_hermann_ids:
            classification = session.get(CropClassification, classification_id)
            assert classification.identity == "Hermann"
            assert classification.source == ClassificationSources.REVIEW

        # --- Scenario 7: predictions update where expected ---
        # The 5 unreviewed "hermann-like" crops should now predict Hermann.
        for crop, _path in crops[25:30]:
            session.refresh(crop.classification)
            assert crop.classification.identity == "Hermann"
            assert crop.classification.source == ClassificationSources.AUTO

        # The legacy no-embedding crop should have been embedded and
        # correctly classified.
        session.refresh(legacy_crop.classification)
        assert legacy_crop.classification.identity == "Fibs"
        assert legacy_crop.classification.embedding is not None

        # The ambiguous crops remain Unknown -- never force a label.
        for crop, _path in crops[30:40]:
            session.refresh(crop.classification)
            assert crop.classification.identity is None

        # --- Scenario 8: rerun with unchanged inputs -> stable results ---
        second_pass = reclassify_service.reclassify()

        assert second_pass.eligible_count == first_pass.eligible_count
        assert second_pass.changed_count == 0

        # --- Scenario 9: add more reviews, reclassify again ---
        for crop, _path in crops[25:30]:
            correction.correct(crop.classification.id, "Hermann")

        third_pass = reclassify_service.reclassify()

        assert third_pass.eligible_count == second_pass.eligible_count - 5

        for crop, _path in crops[25:30]:
            session.refresh(crop.classification)
            assert crop.classification.identity == "Hermann"
            assert crop.classification.source == ClassificationSources.REVIEW


def test_failed_reclassify_job_can_be_retried_without_corruption(engine):
    """Scenario 10: a killed/failed job can be retried without duplicating
    logical records or losing reviewed state."""
    with Session(engine) as session:
        identity = Identity(name="Hermann")
        session.add(identity)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=identity.id,
                crop_path="hermann.jpg",
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
            )
        )

        # No cached embedding: forces the embedder to be called, so a
        # crashing embedder actually exercises the failure path below.
        crop = Crop(detection_id=1, path="new.jpg")
        session.add(crop)
        session.flush()
        session.add(
            CropClassification(
                crop=crop,
                identity=None,
                confidence=-1.0,
                embedding=None,
            )
        )
        session.commit()

        repository = PipelineJobRepository(session)
        service = PipelineJobService(session, repository=repository)

        class FlakyEmbedder:
            def embed_batch(self, paths):
                raise RuntimeError("simulated embedder crash")

        class WorkingEmbedder:
            def embed_batch(self, paths):
                return np.array([[1, 0, 0] for _ in paths], dtype=np.float32)

        def failing_handler(progress):
            return ReclassifyService(session, FlakyEmbedder()).reclassify(
                progress=progress
            )

        failing_runner = PipelineJobRunner(
            repository=repository,
            service=service,
            handlers={PipelineOperation.RECLASSIFY: failing_handler},
        )

        job = service.create_job(operation=PipelineOperation.RECLASSIFY)

        with pytest.raises(RuntimeError):
            failing_runner.run_job(job.id)

        session.refresh(job)
        assert job.status.value == "failed"

        failed_pass = session.query(ClassificationPass).one()
        assert failed_pass.status.value == "failed"

        # Retry: a fresh job with a working embedder must succeed and must
        # not be blocked or corrupted by the earlier failure.
        def working_handler(progress):
            return ReclassifyService(session, WorkingEmbedder()).reclassify(
                progress=progress
            )

        retry_runner = PipelineJobRunner(
            repository=repository,
            service=service,
            handlers={PipelineOperation.RECLASSIFY: working_handler},
        )

        retry_job = service.create_job(operation=PipelineOperation.RECLASSIFY)
        retry_runner.run_job(retry_job.id)

        session.refresh(retry_job)
        assert retry_job.status.value == "completed"

        classification = session.query(CropClassification).one()
        assert classification.identity == "Hermann"

        # Exactly two passes exist: the failed one and the successful retry
        # -- no duplicated logical records.
        assert session.query(ClassificationPass).count() == 2


def test_existing_project_migrates_and_continues_working(tmp_path: Path):
    """Scenario 11: an existing project (pre-dating the v1.0.0 schema
    additions) upgrades cleanly and the review/reclassify loop keeps working."""
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "CREATE TABLE identities (id INTEGER PRIMARY KEY, name VARCHAR(64) NOT NULL UNIQUE)"
    )
    connection.execute(
        "CREATE TABLE embedding_examples ("
        "id INTEGER PRIMARY KEY, identity_id INTEGER, crop_path VARCHAR(512) NOT NULL, "
        "embedding BLOB NOT NULL, source VARCHAR(16) NOT NULL, "
        "created_at DATETIME, captured_at DATETIME)"
    )
    connection.execute(
        "CREATE TABLE crop_classifications ("
        "id INTEGER PRIMARY KEY, crop_id INTEGER, identity VARCHAR(64), "
        "confidence FLOAT NOT NULL, candidates TEXT NOT NULL, source VARCHAR(16) NOT NULL, "
        "created_at DATETIME, matched_example_id INTEGER)"
    )
    connection.execute(
        "CREATE TABLE crops (id INTEGER PRIMARY KEY, detection_id INTEGER, path VARCHAR(512) NOT NULL)"
    )
    connection.execute("INSERT INTO identities (id, name) VALUES (1, 'Hermann')")
    connection.execute(
        "INSERT INTO crops (id, detection_id, path) VALUES (1, 1, 'hermann-crop.jpg')"
    )

    connection.execute(
        "INSERT INTO embedding_examples (identity_id, crop_path, embedding, source) "
        "VALUES (?, ?, ?, ?)",
        (
            1,
            "hermann.jpg",
            np.array([1, 0, 0], dtype=np.float32).tobytes(),
            "BOOTSTRAP",
        ),
    )
    connection.execute(
        "INSERT INTO crop_classifications "
        "(crop_id, identity, confidence, candidates, source) VALUES (?, ?, ?, ?, ?)",
        (1, "Hermann", 0.95, "[]", "REVIEW"),
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        # Pre-existing reviewed data survived the migration untouched.
        existing = session.query(CropClassification).one()
        assert existing.identity == "Hermann"
        assert existing.source == ClassificationSources.REVIEW
        assert existing.classifier_version is None  # column added, old row unaffected

        # The migrated schema must be immediately usable for a new
        # classify + reclassify cycle. A crop with no classification row at
        # all is what "pending" means -- mirrors a freshly detected crop.
        crop = Crop(detection_id=2, path="new-dog.jpg")
        session.add(crop)
        session.commit()

        embedder = FakeVectorEmbedder(
            {"new-dog.jpg": [1.0, 0.0, 0.0], "hermann.jpg": [1.0, 0.0, 0.0]}
        )

        classification_service = ClassificationService(
            session, embedder, IdentityClassifier(session)
        )
        summary = classification_service.classify(mode=ClassificationMode.PENDING)
        assert summary.classified == 1
        assert summary.identities == {"Hermann": 1}

        result = ReclassifyService(session, embedder).reclassify()
        assert result.eligible_count == 1  # only the AUTO row; REVIEW row excluded


def test_mixed_dog_and_cat_project_full_loop(engine):
    """
    DT-1110: the same review -> reclassify -> sync loop DT-1009 covers for a
    dog-only project, but with a dog "Max" and a cat "Max" -- same name,
    same embedding vector -- moving through classify, correction/learning,
    reclassify, and sync together. If species scoping were broken anywhere
    in that chain, this is the scenario that would surface it: identical
    names and vectors give species-blind code nothing else to go on.
    """

    class FakeAlbums:
        def __init__(self):
            self.synced = []

        def sync_identity(self, identity, asset_ids, species="dog"):
            self.synced.append((species, identity, tuple(sorted(asset_ids))))

    with Session(engine) as session:
        path_to_vector: dict[str, list[float]] = {}

        def add_crop(species: str, label: str, immich_id: str) -> Crop:
            path = f"{species}-{label}.jpg"
            path_to_vector[path] = [1.0, 0.0, 0.0]

            asset = Asset(
                immich_asset_id=immich_id, checksum=immich_id, extension=".jpg"
            )
            detection = Detection(
                asset=asset, label=species, confidence=0.95, x1=0, y1=0, x2=10, y2=10
            )
            crop = Crop(detection=detection, path=path, species=species)
            session.add(crop)
            session.flush()
            return crop

        # Two crops per species: one will be reviewed directly, the other
        # left for Reclassify to pick up once examples exist.
        dog_crop = add_crop("dog", "pending", "dog-asset")
        cat_crop = add_crop("cat", "pending", "cat-asset")
        new_dog_crop = add_crop("dog", "new", "dog-asset-2")
        new_cat_crop = add_crop("cat", "new", "cat-asset-2")

        embedder = FakeVectorEmbedder(path_to_vector)

        classification_service = ClassificationService(
            session, embedder, IdentityClassifier(session)
        )
        summary = classification_service.classify(mode=ClassificationMode.PENDING)

        assert summary.classified == 4
        # Zero labeled examples yet -- all Unknown, not cross-matched to
        # whatever the other species might eventually be named.
        assert summary.identities == {"Unknown": 4}

        # Review: teach the classifier "Max" separately for each species.
        learner = Learner(embedder, session)
        correction = ClassificationCorrectionService(session, learner)

        correction.correct(dog_crop.classification.id, "Max")
        correction.correct(cat_crop.classification.id, "Max")

        dog_identity = session.scalar(
            select(Identity).where(Identity.species == Species.DOG)
        )
        cat_identity = session.scalar(
            select(Identity).where(Identity.species == Species.CAT)
        )
        assert dog_identity.name == "Max"
        assert cat_identity.name == "Max"
        assert dog_identity.id != cat_identity.id

        # The still-Unknown, AUTO-sourced crops of each species -- identical
        # vector -- must each resolve to their own species' "Max" once
        # Reclassify picks them up, never the other's.
        result = ReclassifyService(session, embedder).reclassify()

        assert result.eligible_count == 2

        session.refresh(new_dog_crop.classification)
        session.refresh(new_cat_crop.classification)

        assert new_dog_crop.classification.identity == "Max"
        assert new_cat_crop.classification.identity == "Max"
        assert (
            new_dog_crop.classification.matched_example_id
            != new_cat_crop.classification.matched_example_id
        )

        # Rerunning changes nothing -- idempotent across both species.
        second = ReclassifyService(session, embedder).reclassify()
        assert second.changed_count == 0

        # Sync: two "Max" identities must produce two separate albums, not
        # one merged album with both species' assets.
        albums = FakeAlbums()
        sync_summary = SyncService(
            session, albums, SyncPolicy(minimum_confidence=0.0)
        ).sync()

        assert len(sync_summary.identities) == 2
        assert sorted(albums.synced) == [
            ("cat", "Max", ("cat-asset", "cat-asset-2")),
            ("dog", "Max", ("dog-asset", "dog-asset-2")),
        ]


def test_re_correction_after_sync_fixes_stale_album_membership(engine):
    """
    DT-1113: the interview's stated pain point was a photo left in the
    wrong Immich album after a correction. This exercises the real chain --
    classify -> correct -> sync -> correct again -> sync again -- and
    asserts the *album* state ends up correct, not just the classification
    row. A test that only checked CropClassification.identity would miss
    exactly the bug this ticket fixes: sync_identity() only ever adds, so
    without the removal path the asset would end up in both albums.
    """

    class FakeAlbums:
        def __init__(self):
            self.albums: dict[str, set[str]] = {}

        def _key(self, identity, species):
            return f"{species} - {identity}"

        def sync_identity(self, identity, asset_ids, species="dog"):
            self.albums.setdefault(self._key(identity, species), set()).update(
                asset_ids
            )

        def remove_from_identity(self, identity, asset_ids, species="dog"):
            key = self._key(identity, species)
            if key in self.albums:
                self.albums[key].difference_update(asset_ids)

    with Session(engine) as session:
        path_to_vector = {"fibs.jpg": [1.0, 0.0, 0.0]}

        asset = Asset(immich_asset_id="dog-asset-1", checksum="c1", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=0.95, x1=0, y1=0, x2=10, y2=10
        )
        crop = Crop(detection=detection, path="fibs.jpg", species=Species.DOG)
        session.add(crop)
        session.flush()

        embedder = FakeVectorEmbedder(path_to_vector)

        classification_service = ClassificationService(
            session, embedder, IdentityClassifier(session)
        )
        classification_service.classify(mode=ClassificationMode.PENDING)

        learner = Learner(embedder, session)
        correction = ClassificationCorrectionService(session, learner)

        correction.correct(crop.classification.id, "Fibs")

        albums = FakeAlbums()
        policy = SyncPolicy(minimum_confidence=0.0)

        SyncService(session, albums, policy).sync()

        assert albums.albums["dog - Fibs"] == {"dog-asset-1"}

        # A second, later correction on an already-synced asset -- the
        # exact scenario the interview described.
        correction.correct(crop.classification.id, "Hermann")

        SyncService(session, albums, policy).sync()

        assert albums.albums["dog - Fibs"] == set()
        assert albums.albums["dog - Hermann"] == {"dog-asset-1"}


def test_cluster_approval_survives_reclassification(engine):
    """
    Issue #141: approving a cluster is N ordinary corrections, so the loop
    that already holds for single reviews must hold for a bulk approval --
    reclassify after an approval is idempotent and never mutates a label
    the approval established.
    """
    with Session(engine) as session:
        path_to_vector: dict[str, list[float]] = {}

        def add_crop(name: str, vector: list[float]) -> Crop:
            path_to_vector[name] = vector
            asset = Asset(immich_asset_id=f"asset-{name}", extension=".jpg")
            detection = Detection(
                asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=10, y2=10
            )
            crop = Crop(detection=detection, path=name, species=Species.DOG)
            session.add(crop)
            session.flush()
            return crop

        # One identity with a single seed example, so its pending crops are
        # candidates rather than confident matches.
        session.add(Identity(name="Fibs", species=Species.DOG))
        session.flush()

        seed = add_crop("fibs-seed.jpg", [1.0, 0.0, 0.0])
        cluster_crops = [
            add_crop(f"fibs-{index}.jpg", [1.0, 0.02 * index, 0.0])
            for index in range(5)
        ]
        other = add_crop("hermann-0.jpg", [0.0, 1.0, 0.0])

        session.commit()

        embedder = FakeVectorEmbedder(path_to_vector)
        learner = Learner(embedder, session)
        correction = ClassificationCorrectionService(session, learner)

        ClassificationService(session, embedder, IdentityClassifier(session)).classify(
            mode=ClassificationMode.PENDING
        )

        # Bootstrap through the Review tab, exactly as the owner would.
        correction.correct(seed.classification.id, "Fibs")
        correction.correct(other.classification.id, "Hermann")

        ReclassifyService(session, IdentityClassifier(session)).reclassify()

        proposal = RecommendationClusterService(session).clusters(
            identity="Fibs",
            species=Species.DOG,
        )

        pending_ids = {crop.classification.id for crop in cluster_crops}

        assert proposal.candidate_count == len(pending_ids)

        cluster = proposal.clusters[0]

        assert cluster.size == len(pending_ids)

        summary = ClusterApprovalService(session, correction).approve(
            identity="Fibs",
            species=Species.DOG,
            classification_ids=[member.classification_id for member in cluster.members],
        )

        assert summary.applied == len(pending_ids)
        assert summary.skipped == 0

        # N members -> N review actions and N reference examples, the same
        # shape N single corrections from the Review page would leave.
        assert session.query(ReviewAction).filter(
            ReviewAction.classification_id.in_(pending_ids)
        ).count() == len(pending_ids)
        assert session.query(EmbeddingExample).filter(
            EmbeddingExample.crop_path.in_(
                [crop.path for crop in cluster_crops],
            )
        ).count() == len(pending_ids)

        approved = {
            classification.id: classification.identity
            for classification in session.query(CropClassification).all()
        }

        # Reclassification is derived state and must never rewrite a human
        # decision -- twice over, to pin idempotency.
        for _ in range(2):
            ReclassifyService(session, IdentityClassifier(session)).reclassify()

            for classification in session.query(CropClassification).all():
                assert classification.identity == approved[classification.id]

            for classification_id in pending_ids:
                classification = session.get(CropClassification, classification_id)

                assert classification.identity == "Fibs"
                assert classification.confidence == 1.0
                assert classification.source == ClassificationSources.REVIEW

        # And the approved crops have left the candidate pool.
        assert (
            RecommendationClusterService(session)
            .clusters(identity="Fibs", species=Species.DOG)
            .candidate_count
            == 0
        )
