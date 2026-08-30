"""
Issue #179: paste an Immich photo link, see what this instance already
knows about that photo. See docs/specs/photo-lookup.md.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import Species
from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection
from immich_dog_tagger.services.photo_lookup import PhotoLookupService


def test_get_returns_none_for_unknown_asset(engine):
    with Session(engine) as session:
        assert PhotoLookupService(session).get("does-not-exist") is None


def test_get_returns_asset_with_no_detections(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            extension=".jpg",
            captured_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        session.add(asset)
        session.commit()

        lookup = PhotoLookupService(session).get("asset-1")

        assert lookup is not None
        assert lookup.asset_id == asset.id
        assert lookup.detections == []


def test_get_includes_detection_box_and_classification(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-2",
            extension=".jpg",
            captured_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.9,
            x1=10,
            y1=20,
            x2=110,
            y2=220,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
            species=Species.DOG,
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.87,
        )

        session.add(classification)
        session.commit()

        lookup = PhotoLookupService(session).get("asset-2")

        assert lookup is not None
        assert len(lookup.detections) == 1

        item = lookup.detections[0]
        assert (item.x1, item.y1, item.x2, item.y2) == (10, 20, 110, 220)
        assert item.species == "dog"
        assert item.crop_id == crop.id
        assert item.classification_id == classification.id
        assert item.identity == "Fibs"
        assert item.confidence == 0.87
        assert item.not_animal is False


def test_get_includes_not_animal_flag(engine):
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset-not-animal", extension=".jpg")

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=50,
            y2=50,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
            species=Species.DOG,
            not_animal=True,
        )

        session.add(crop)
        session.commit()

        lookup = PhotoLookupService(session).get("asset-not-animal")

        assert lookup is not None
        assert lookup.detections[0].not_animal is True


def test_get_handles_detection_with_no_classification_yet(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-3",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=50,
            y2=50,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        session.add(crop)
        session.commit()

        lookup = PhotoLookupService(session).get("asset-3")

        assert lookup is not None
        item = lookup.detections[0]
        assert item.classification_id is None
        assert item.identity is None
        assert item.confidence is None
