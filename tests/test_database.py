import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus, PipelineOperation
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
