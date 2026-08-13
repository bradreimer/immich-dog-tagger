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
        species="dog",
    ):
        self.calls.append(
            (
                identity,
                asset_ids,
                species,
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

        assert summary.identities[0].identity == "Hermann"
        assert summary.identities[0].assets == 1

        assert albums.calls == [
            (
                "Hermann",
                ["asset1"],
                "dog",
            )
        ]


def test_sync_keeps_same_named_dog_and_cat_separate(engine):
    # Regression test (DT-1110): before species-scoping, this aggregation
    # was keyed by identity name alone, so a dog "Max" and a cat "Max"
    # would silently merge into one album with both species' assets.
    with Session(engine) as session:
        dog_asset = Asset(immich_asset_id="dog-asset", checksum="a", extension=".jpg")
        cat_asset = Asset(immich_asset_id="cat-asset", checksum="b", extension=".jpg")

        dog_detection = Detection(
            asset=dog_asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )
        cat_detection = Detection(
            asset=cat_asset, label="cat", confidence=1.0, x1=0, y1=0, x2=10, y2=10
        )

        dog_crop = Crop(detection=dog_detection, path="dog.jpg", species="dog")
        cat_crop = Crop(detection=cat_detection, path="cat.jpg", species="cat")

        session.add(CropClassification(crop=dog_crop, identity="Max", confidence=0.95))
        session.add(CropClassification(crop=cat_crop, identity="Max", confidence=0.95))
        session.commit()

        albums = FakeAlbums()

        summary = SyncService(session, albums).sync()

        assert len(summary.identities) == 2

        by_species = {item.species: item for item in summary.identities}

        assert by_species["dog"].identity == "Max"
        assert by_species["dog"].assets == 1
        assert by_species["cat"].identity == "Max"
        assert by_species["cat"].assets == 1

        assert sorted(albums.calls) == [
            ("Max", ["cat-asset"], "cat"),
            ("Max", ["dog-asset"], "dog"),
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

        assert summary.identities[0].identity == "Fibs"
        assert summary.identities[0].assets == 1

        assert albums.calls == []
