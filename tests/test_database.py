import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus, PipelineOperation, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
    PipelineJob,
)


def test_database_creation(engine, tmp_path: Path):
    assert (tmp_path / "state.db").exists()

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
        )
        session.add(asset)
        session.commit()

        result = session.query(Asset).one()

        assert result.immich_asset_id == "abc123"
        assert result.checksum == "xyz"
        assert result.status is AssetStatus.PENDING

        identity = Identity(
            name="Hermann",
        )

        session.add(identity)
        session.commit()

        embedding = EmbeddingExample(
            identity_id=identity.id,
            crop_path="crops/hermann_001.jpg",
            embedding=b"\x01\x02\x03",
            source=EmbeddingSources.BOOTSTRAP,
        )

        session.add(embedding)
        session.commit()

        result = session.query(EmbeddingExample).one()

        assert result.crop_path == ("crops/hermann_001.jpg")

        assert result.embedding == (b"\x01\x02\x03")

        assert result.identity.name == ("Hermann")


def test_crop_classification_persistence(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="checksum",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.99,
            x1=0,
            y1=0,
            x2=100,
            y2=100,
        )

        crop = Crop(
            detection=detection,
            path="test.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        result = session.query(CropClassification).one()

        assert result.identity == "Hermann"
        assert result.crop.path == "test.jpg"
        assert result.crop.detection.label == "dog"


def test_database_existing_models_unchanged_with_pipeline_jobs(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-existing-model",
            checksum="checksum",
            extension=".jpg",
        )
        session.add(asset)

        job = PipelineJob(operation=PipelineOperation.SCAN)
        session.add(job)

        session.commit()

        persisted_asset = session.query(Asset).one()
        persisted_job = session.query(PipelineJob).one()

        assert persisted_asset.immich_asset_id == "asset-existing-model"
        assert persisted_asset.status is AssetStatus.PENDING
        assert persisted_job.operation is PipelineOperation.SCAN


def test_database_adds_identity_activation_column(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    connection.execute(
        "CREATE TABLE identities (id INTEGER PRIMARY KEY, name VARCHAR(64) NOT NULL UNIQUE)"
    )
    connection.execute(
        "INSERT INTO identities (name) VALUES (?)",
        ("Fibs",),
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        rows = session.execute(
            text("SELECT name, is_active FROM identities ORDER BY id")
        ).all()

    assert rows == [("Fibs", 1)]


def test_database_adds_classification_pass_columns(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    connection.execute(
        "CREATE TABLE crop_classifications ("
        "id INTEGER PRIMARY KEY, "
        "crop_id INTEGER, "
        "identity VARCHAR(64), "
        "confidence FLOAT NOT NULL, "
        "candidates TEXT NOT NULL, "
        "source VARCHAR(16) NOT NULL"
        ")"
    )
    connection.execute(
        "INSERT INTO crop_classifications "
        "(crop_id, identity, confidence, candidates, source) VALUES (?, ?, ?, ?, ?)",
        (1, "Hermann", 0.95, "[]", "auto"),
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        rows = session.execute(
            text(
                "SELECT identity, classifier_version, classification_pass_id, embedding "
                "FROM crop_classifications ORDER BY id"
            )
        ).all()

    assert rows == [("Hermann", None, None, None)]


def test_database_adds_classification_pass_trend_columns(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    connection.execute(
        "CREATE TABLE classification_passes ("
        "id INTEGER PRIMARY KEY, "
        "status VARCHAR(16) NOT NULL, "
        "classifier_version VARCHAR(32) NOT NULL, "
        "threshold FLOAT NOT NULL, "
        "eligible_count INTEGER NOT NULL, "
        "confident_count INTEGER NOT NULL, "
        "needs_review_count INTEGER NOT NULL, "
        "unknown_count INTEGER NOT NULL, "
        "changed_count INTEGER NOT NULL"
        ")"
    )
    connection.execute(
        "INSERT INTO classification_passes "
        "(status, classifier_version, threshold, eligible_count, confident_count, "
        "needs_review_count, unknown_count, changed_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("completed", "v1", 0.80, 10, 8, 0, 2, 1),
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        rows = session.execute(
            text(
                "SELECT status, labeled_example_count, review_queue_size "
                "FROM classification_passes ORDER BY id"
            )
        ).all()

    assert rows == [("completed", None, None)]


def test_database_adds_identity_species_column_and_scopes_uniqueness(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    # Oldest pre-DT-1110 shape: no is_active, no species, name unique alone.
    connection.execute(
        "CREATE TABLE identities (id INTEGER PRIMARY KEY, name VARCHAR(64) NOT NULL UNIQUE)"
    )
    connection.execute(
        "INSERT INTO identities (name) VALUES (?)",
        ("Fibs",),
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        existing = session.scalars(select(Identity)).all()

        assert len(existing) == 1
        assert existing[0].name == "Fibs"
        assert existing[0].species == Species.DOG
        assert existing[0].is_active is True

        # Composite (species, name) uniqueness: a cat "Fibs" is a different
        # identity from the migrated dog "Fibs" and must not collide.
        session.add(Identity(name="Fibs", species=Species.CAT))
        session.commit()

        assert (
            session.scalar(
                select(func.count())
                .select_from(Identity)
                .where(Identity.name == "Fibs")
            )
            == 2
        )

        # Same-species duplicate is still rejected.
        session.add(Identity(name="Fibs", species=Species.DOG))

        with pytest.raises(IntegrityError):
            session.commit()


def test_database_adds_crop_species_column(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    connection.execute(
        "CREATE TABLE detections ("
        "id INTEGER PRIMARY KEY, asset_id INTEGER, label VARCHAR NOT NULL, "
        "confidence FLOAT NOT NULL, x1 INTEGER, y1 INTEGER, x2 INTEGER, y2 INTEGER"
        ")"
    )
    connection.execute(
        "CREATE TABLE crops (id INTEGER PRIMARY KEY, detection_id INTEGER, path VARCHAR(512) NOT NULL)"
    )
    connection.execute(
        "INSERT INTO detections (id, asset_id, label, confidence, x1, y1, x2, y2) "
        "VALUES (1, 1, 'dog', 0.9, 0, 0, 10, 10)"
    )
    connection.execute(
        "INSERT INTO crops (id, detection_id, path) VALUES (1, 1, 'fibs.jpg')"
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        rows = session.execute(
            text("SELECT path, species FROM crops ORDER BY id")
        ).all()

    assert rows == [("fibs.jpg", "DOG")]


def test_database_adds_pipeline_job_visible_column(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    # Pre-DT-1116 shape: no visible column yet.
    connection.execute(
        "CREATE TABLE pipeline_jobs ("
        "id INTEGER PRIMARY KEY, "
        "operation VARCHAR(32) NOT NULL, "
        "status VARCHAR(16) NOT NULL, "
        "progress_current INTEGER NOT NULL DEFAULT 0, "
        "progress_total INTEGER, "
        "progress_message VARCHAR(512), "
        "error_message VARCHAR(2048)"
        ")"
    )
    connection.execute(
        "INSERT INTO pipeline_jobs (operation, status) VALUES ('scan', 'completed')"
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        rows = session.execute(
            text("SELECT operation, visible FROM pipeline_jobs ORDER BY id")
        ).all()

    # Existing jobs stay visible on migration -- clearing is something an
    # operator does going forward, not a retroactive change.
    assert rows == [("scan", 1)]


def test_database_adds_pipeline_job_heartbeat_column(tmp_path: Path):
    database_path = tmp_path / "state.db"
    connection = sqlite3.connect(database_path)

    # Pre-#134 shape: no heartbeat_at column yet.
    connection.execute(
        "CREATE TABLE pipeline_jobs ("
        "id INTEGER PRIMARY KEY, "
        "operation VARCHAR(32) NOT NULL, "
        "status VARCHAR(16) NOT NULL, "
        "progress_current INTEGER NOT NULL DEFAULT 0, "
        "progress_total INTEGER, "
        "progress_message VARCHAR(512), "
        "error_message VARCHAR(2048), "
        "created_at DATETIME NOT NULL, "
        "started_at DATETIME, "
        "completed_at DATETIME, "
        "schedule_id INTEGER"
        ")"
    )
    connection.execute(
        "INSERT INTO pipeline_jobs (operation, status, created_at, started_at) "
        "VALUES ('SCAN', 'RUNNING', '2026-08-01 10:00:00', '2026-08-01 10:00:05')"
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        job = session.scalars(select(PipelineJob)).one()

        # Not backfilled: an already-running job keeps its real age via
        # started_at rather than looking freshly alive.
        assert job.heartbeat_at is None
        assert job.last_activity_at == job.started_at


def test_database_adds_asset_metadata_columns_without_losing_classifications(
    tmp_path: Path,
):
    """
    Issue #94's cached Immich location/people/favorite fields must land on an
    existing library by migration, not by recreating `state.db` -- the
    accumulated classification and review history in there cannot be
    regenerated.

    Rather than hand-writing a stale schema, this builds a current database,
    drops the #94 columns to reproduce the pre-#94 `assets` shape, and
    reopens it: every pre-existing row (including the classification) has to
    survive, with the new columns defaulted rather than populated with
    guesses.
    """

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.PENDING,
        )
        session.add(asset)
        session.flush()

        detection = Detection(
            asset_id=asset.id,
            label="dog",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )
        session.add(detection)
        session.flush()

        crop = Crop(detection_id=detection.id, path="hermann.jpg", species=Species.DOG)
        session.add(crop)
        session.flush()

        session.add(
            CropClassification(
                crop_id=crop.id,
                identity="Hermann",
                confidence=0.87,
            )
        )
        session.commit()

    engine.dispose()

    # Reproduce the pre-#94 `assets` shape.
    metadata_columns = (
        "latitude",
        "longitude",
        "country",
        "state",
        "city",
        "is_favorite",
        "people",
        "metadata_synced_at",
    )

    connection = sqlite3.connect(tmp_path / "state.db")

    for column in metadata_columns:
        connection.execute(f"ALTER TABLE assets DROP COLUMN {column}")

    connection.commit()
    connection.close()

    engine = create_database(tmp_path)

    with Session(engine) as session:
        migrated = session.scalar(select(Asset))

        assert migrated is not None
        assert migrated.immich_asset_id == "asset-1"
        assert migrated.latitude is None
        assert migrated.city is None
        assert migrated.is_favorite is False
        assert migrated.people == []
        assert migrated.metadata_synced_at is None

        classification = session.scalar(select(CropClassification))

        assert classification is not None
        assert classification.identity == "Hermann"
        assert classification.confidence == 0.87


def test_engine_waits_for_a_concurrent_writer_instead_of_failing_immediately(
    tmp_path: Path,
):
    # Regression test for issue #104: with no busy_timeout configured, any
    # connection that landed on another writer's lock window (even a brief
    # one, e.g. a batch commit) failed immediately with "database is
    # locked" instead of waiting the moment it takes for that lock to
    # clear.
    import threading
    import time

    from immich_dog_tagger.database import create_database
    from immich_dog_tagger.models import Identity

    engine = create_database(tmp_path)

    # check_same_thread=False: the connection is created here but committed
    # from the releaser thread below -- safe since only one thread ever
    # touches it at a time (the two are joined, not run concurrently).
    blocker = sqlite3.connect(
        str(tmp_path / "state.db"), timeout=0, check_same_thread=False
    )
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute(
        "INSERT INTO identities (species, name, is_active) VALUES ('DOG', 'Blocker', 1)"
    )

    def release_after_delay():
        time.sleep(0.5)
        blocker.commit()
        blocker.close()

    releaser = threading.Thread(target=release_after_delay)
    releaser.start()

    started = time.monotonic()

    with Session(engine) as session:
        session.add(Identity(name="Waiter"))
        session.commit()

    elapsed = time.monotonic() - started
    releaser.join()

    # It waited for the blocker's lock to clear rather than raising
    # "database is locked" the instant it hit contention.
    assert elapsed >= 0.4

    with Session(engine) as verify_session:
        names = {identity.name for identity in verify_session.query(Identity).all()}

    assert names == {"Blocker", "Waiter"}


def test_database_uses_wal_journal_mode(tmp_path: Path):
    # Regression test for issue #107: state.db must run in WAL mode, not
    # SQLite's default rollback journal, so readers and a writer can
    # proceed concurrently.
    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with engine.connect() as connection:
        mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()

    assert mode == "wal"


def test_writer_is_not_blocked_by_a_concurrent_long_lived_reader(tmp_path: Path):
    # Regression test for issue #107: batching commits and adding a
    # busy_timeout (#104) only shrank the window during which a pipeline
    # job's read transaction could block a writer -- for a long-running
    # batch (a slow download, an embedding pass) that window can still
    # exceed the busy_timeout, surfacing as "database is locked" for an
    # unrelated write like creating a dog. WAL mode removes the contention
    # entirely: a writer isn't blocked by any reader's open transaction.
    import threading
    import time

    from immich_dog_tagger.database import create_database
    from immich_dog_tagger.models import Identity

    engine = create_database(tmp_path)

    with Session(engine) as session:
        session.add(Identity(name="Existing"))
        session.commit()

    # check_same_thread=False: the connection is created here but committed
    # from the releaser thread below -- safe since only one thread ever
    # touches it at a time (the two are joined, not run concurrently).
    reader = sqlite3.connect(
        str(tmp_path / "state.db"), timeout=0, check_same_thread=False
    )
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM identities").fetchall()

    def release_after_delay():
        time.sleep(0.5)
        reader.commit()
        reader.close()

    releaser = threading.Thread(target=release_after_delay)
    releaser.start()

    started = time.monotonic()

    with Session(engine) as session:
        session.add(Identity(name="Writer"))
        session.commit()

    elapsed = time.monotonic() - started
    releaser.join()

    # The write went through immediately rather than waiting out the
    # reader's still-open transaction -- proof WAL mode, not just
    # busy_timeout, is what let it through.
    assert elapsed < 0.4

    with Session(engine) as verify_session:
        names = {identity.name for identity in verify_session.query(Identity).all()}

    assert names == {"Existing", "Writer"}


def test_database_adds_identity_merges_table_to_an_existing_database(tmp_path: Path):
    """
    Issue #148 adds a new table rather than changing an existing one, so an
    existing state.db picks it up from create_all with no data migration --
    but only if create_database is actually re-run against it.
    """
    from immich_dog_tagger.database import create_database

    create_database(tmp_path)

    connection = sqlite3.connect(tmp_path / "state.db")
    connection.execute("DROP TABLE identity_merges")
    connection.commit()
    connection.close()

    engine = create_database(tmp_path)

    with Session(engine) as session:
        count = session.execute(text("SELECT COUNT(*) FROM identity_merges")).scalar()

    assert count == 0
