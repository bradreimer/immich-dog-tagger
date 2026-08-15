from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    Identity,
    PetOccurrence,
)
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService

_next_asset_id = 0


def _make_classification(
    session: Session,
    *,
    identity: str | None,
    species: Species = Species.DOG,
    confidence: float = 0.9,
    source: ClassificationSources = ClassificationSources.AUTO,
    with_asset: bool = True,
) -> CropClassification:
    global _next_asset_id
    _next_asset_id += 1

    if with_asset:
        asset = Asset(immich_asset_id=f"a{_next_asset_id}", extension=".jpg")
        session.add(asset)
        session.flush()

        detection = Detection(
            asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        session.add(detection)
        session.flush()
        detection_id = detection.id
    else:
        # A dangling FK (no matching Detection row), not None -- Crop.detection_id
        # is NOT NULL. SQLite doesn't enforce the FK here, so crop.detection
        # simply resolves to None, exercising the "no asset context" path.
        detection_id = 999999

    crop = Crop(detection_id=detection_id, path="crop.jpg", species=species)
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=identity,
        confidence=confidence,
        source=source,
    )
    session.add(classification)
    session.commit()

    return classification


def test_sync_classification_creates_occurrence(session):
    session.add(Identity(name="Hermann", species=Species.DOG))
    session.commit()

    classification = _make_classification(session, identity="Hermann")

    PetOccurrenceService(session).sync_classification(classification)
    session.commit()

    occurrence = session.query(PetOccurrence).one()
    assert occurrence.crop_classification_id == classification.id
    assert occurrence.confidence == 0.9
    assert occurrence.source == ClassificationSources.AUTO


def test_sync_classification_ignores_unresolved_identity(session):
    classification = _make_classification(session, identity=None)

    PetOccurrenceService(session).sync_classification(classification)
    session.commit()

    assert session.query(PetOccurrence).count() == 0


def test_sync_classification_ignores_unknown(session):
    classification = _make_classification(session, identity="Unknown")

    PetOccurrenceService(session).sync_classification(classification)
    session.commit()

    assert session.query(PetOccurrence).count() == 0


def test_sync_classification_removes_occurrence_when_cleared(session):
    session.add(Identity(name="Hermann", species=Species.DOG))
    session.commit()

    classification = _make_classification(session, identity="Hermann")
    service = PetOccurrenceService(session)

    service.sync_classification(classification)
    session.commit()
    assert session.query(PetOccurrence).count() == 1

    classification.identity = None
    service.sync_classification(classification)
    session.commit()

    assert session.query(PetOccurrence).count() == 0


def test_sync_classification_updates_in_place_on_correction(session):
    session.add(Identity(name="Hermann", species=Species.DOG))
    session.add(Identity(name="Biscuit", species=Species.DOG))
    session.commit()

    classification = _make_classification(session, identity="Hermann", confidence=0.6)
    service = PetOccurrenceService(session)

    service.sync_classification(classification)
    session.commit()
    assert session.query(PetOccurrence).count() == 1

    classification.identity = "Biscuit"
    classification.confidence = 1.0
    classification.source = ClassificationSources.REVIEW
    service.sync_classification(classification)
    session.commit()

    occurrences = session.query(PetOccurrence).all()
    assert len(occurrences) == 1
    assert occurrences[0].identity.name == "Biscuit"
    assert occurrences[0].confidence == 1.0
    assert occurrences[0].source == ClassificationSources.REVIEW


def test_sync_classification_skips_unregistered_identity(session):
    # No Identity row named "Ghost" exists -- fail open rather than raise.
    classification = _make_classification(session, identity="Ghost")

    PetOccurrenceService(session).sync_classification(classification)
    session.commit()

    assert session.query(PetOccurrence).count() == 0


def test_sync_classification_skips_crop_without_asset(session):
    classification = _make_classification(session, identity="Hermann", with_asset=False)

    PetOccurrenceService(session).sync_classification(classification)
    session.commit()

    assert session.query(PetOccurrence).count() == 0


def test_sync_all_backfills_existing_classifications(session):
    session.add(Identity(name="Hermann", species=Species.DOG))
    session.commit()

    _make_classification(session, identity="Hermann")
    _make_classification(session, identity=None)

    processed = PetOccurrenceService(session).sync_all()

    assert processed == 2
    assert session.query(PetOccurrence).count() == 1
