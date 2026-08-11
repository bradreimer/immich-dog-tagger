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
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationMode,
    ClassificationSources,
    EmbeddingSources,
    PipelineOperation,
)
from immich_dog_tagger.models import (
    ClassificationPass,
    Crop,
    CropClassification,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.reclassify import ReclassifyService


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
