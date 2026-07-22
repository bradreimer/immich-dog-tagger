from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
)

from immich_dog_tagger.services.sync import SyncService


class FakeAlbums:
    def __init__(self):
        self.calls = []

    def sync_identity(
        self,
        identity,
        asset_ids,
    ):
        self.calls.append(
            (
                identity,
                asset_ids,
            )
        )


def test_sync_groups_assets(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="abc",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=1.0,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        albums = FakeAlbums()

        summary = SyncService(
            session,
            albums,
        ).sync()

        assert summary == {
            "Hermann": 1,
        }

        assert albums.calls == [
            (
                "Hermann",
                ["asset1"],
            )
        ]


def test_sync_dry_run_does_not_update(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="abc",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=1.0,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        albums = FakeAlbums()

        summary = SyncService(
            session,
            albums,
        ).sync(
            dry_run=True,
        )

        assert summary == {
            "Fibs": 1,
        }

        assert albums.calls == []
