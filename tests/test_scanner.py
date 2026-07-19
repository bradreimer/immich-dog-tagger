from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import Asset
from immich_dog_tagger.immich import ImmichAsset
from immich_dog_tagger.scanner import Scanner


class FakeImmich:
    def list_assets(self):
        return [
            ImmichAsset(
                id="abc123",
                filename="dog.jpg",
                checksum="xyz",
            )
        ]


def test_scanner_is_incremental(engine):
    with Session(engine) as session:
        scanner = Scanner(
            FakeImmich(),
            session,
        )

        assert scanner.scan() == 1
        assert scanner.scan() == 0

        asset = session.scalar(select(Asset))

        assert asset is not None
        assert asset.immich_asset_id == "abc123"
        assert asset.checksum == "xyz"
