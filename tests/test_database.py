from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.models import Asset


def test_database_creation(tmp_path: Path):
    engine = create_database(tmp_path)

    assert (tmp_path / "state.db").exists()

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
        )

        session.add(asset)
        session.commit()

        result = session.query(Asset).one()

        assert result.immich_asset_id == "abc123"
        assert result.checksum == "xyz"
        assert result.status == "pending"