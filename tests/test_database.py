from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.models import (
    Asset,
    Identity,
    EmbeddingExample,
)
from immich_dog_tagger.status import AssetStatus


def test_database_creation(tmp_path: Path):
    engine = create_database(tmp_path)

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
        )

        session.add(embedding)
        session.commit()

        result = session.query(
            EmbeddingExample
        ).one()

        assert result.crop_path == (
            "crops/hermann_001.jpg"
        )

        assert result.embedding == (
            b"\x01\x02\x03"
        )

        assert result.identity.name == (
            "Hermann"
        )