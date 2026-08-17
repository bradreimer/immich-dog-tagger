from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    Identity,
)
from immich_dog_tagger.services.insights import IdentityNotFoundError, InsightsService
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService


def _add_occurrence(
    session: Session,
    service: PetOccurrenceService,
    *,
    identity_name: str,
    immich_asset_id: str,
    captured_at: datetime | None = None,
    city: str | None = None,
    country: str | None = None,
    is_favorite: bool = False,
    people: list[dict] | None = None,
) -> None:
    asset = Asset(
        immich_asset_id=immich_asset_id,
        extension=".jpg",
        captured_at=captured_at,
        city=city,
        country=country,
        is_favorite=is_favorite,
        people=people or [],
    )
    session.add(asset)
    session.flush()

    detection = Detection(
        asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
    )
    session.add(detection)
    session.flush()

    crop = Crop(
        detection_id=detection.id, path=f"{immich_asset_id}.jpg", species=Species.DOG
    )
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=identity_name,
        confidence=0.9,
        source=ClassificationSources.AUTO,
    )
    session.add(classification)
    session.commit()

    service.sync_classification(classification)
    session.commit()


def test_summary_raises_for_missing_identity(session):
    with pytest.raises(IdentityNotFoundError):
        InsightsService(session).summary(999)


def test_summary_with_no_occurrences_is_all_zero(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    summary = InsightsService(session).summary(identity.id)

    assert summary.total_photos == 0
    assert summary.first_seen is None
    assert summary.last_seen is None
    assert summary.top_place is None
    assert summary.top_person is None
    assert summary.favorite_photo_count == 0


def test_summary_computes_counts_and_top_place_and_person(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a1",
        captured_at=datetime(2023, 1, 1, tzinfo=UTC),
        city="Seattle",
        country="United States",
        is_favorite=True,
        people=[{"id": "p1", "name": "Brad"}],
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a2",
        captured_at=datetime(2023, 6, 1, tzinfo=UTC),
        city="Seattle",
        country="United States",
        people=[{"id": "p1", "name": "Brad"}, {"id": "p2", "name": "Jane"}],
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a3",
        captured_at=datetime(2024, 3, 1, tzinfo=UTC),
        city="Paris",
        country="France",
        people=[{"id": "p2", "name": "Jane"}],
    )

    insights = InsightsService(session)
    summary = insights.summary(identity.id)

    assert summary.total_photos == 3
    assert summary.first_seen == datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    assert summary.last_seen == datetime(2024, 3, 1, tzinfo=UTC).replace(tzinfo=None)
    assert summary.photos_by_year == {2023: 2, 2024: 1}
    assert summary.top_place is not None
    assert summary.top_place.city == "Seattle"
    assert summary.top_place.count == 2
    assert summary.top_person is not None
    assert summary.top_person.person_id == "p1"
    assert summary.top_person.count == 2
    assert summary.favorite_photo_count == 1

    places = insights.places(identity.id)
    assert [p.city for p in places] == ["Seattle", "Paris"]

    people = insights.people(identity.id)
    assert {p.person_id for p in people} == {"p1", "p2"}

    timeline = insights.timeline(identity.id)
    assert [entry.immich_asset_id for entry in timeline] == ["a1", "a2", "a3"]


def test_timeline_paginates(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    for i in range(5):
        _add_occurrence(
            session,
            service,
            identity_name="Hermann",
            immich_asset_id=f"a{i}",
            captured_at=datetime(2023, 1, i + 1, tzinfo=UTC),
        )

    insights = InsightsService(session)

    first_page = insights.timeline(identity.id, limit=2, offset=0)
    second_page = insights.timeline(identity.id, limit=2, offset=2)

    assert [e.immich_asset_id for e in first_page] == ["a0", "a1"]
    assert [e.immich_asset_id for e in second_page] == ["a2", "a3"]


def test_cards_raises_for_missing_identity(session):
    with pytest.raises(IdentityNotFoundError):
        InsightsService(session).cards(999)


def test_cards_empty_for_identity_with_no_occurrences(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    assert InsightsService(session).cards(identity.id) == []


def test_cards_includes_favourite_place_human_and_favorites(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a1",
        captured_at=datetime(2023, 1, 1, tzinfo=UTC),
        city="Seattle",
        country="United States",
        is_favorite=True,
        people=[{"id": "p1", "name": "Brad"}],
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a2",
        captured_at=datetime(2023, 6, 1, tzinfo=UTC),
        city="Seattle",
        country="United States",
        people=[{"id": "p1", "name": "Brad"}],
    )

    cards = InsightsService(session).cards(identity.id)
    by_slug = {card.slug: card for card in cards}

    assert by_slug["favourite-place"].value == "Seattle, United States"
    assert by_slug["favourite-human"].value == "Brad"
    assert by_slug["immich-favorites"].value == "1"
    # only 2 confirmed photos -- below the smallest milestone threshold
    assert "milestone-total-photos" not in by_slug


def test_cards_includes_milestone_once_threshold_reached(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    for i in range(100):
        _add_occurrence(
            session,
            service,
            identity_name="Hermann",
            immich_asset_id=f"milestone-{i}",
            captured_at=datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i),
        )

    cards = InsightsService(session).cards(identity.id)
    milestone = next(card for card in cards if card.slug == "milestone-total-photos")

    assert milestone.value == "100th confirmed photo"


def test_insights_only_include_this_identitys_occurrences(session):
    hermann = Identity(name="Hermann", species=Species.DOG)
    biscuit = Identity(name="Biscuit", species=Species.DOG)
    session.add_all([hermann, biscuit])
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(session, service, identity_name="Hermann", immich_asset_id="a1")
    _add_occurrence(session, service, identity_name="Biscuit", immich_asset_id="a2")

    insights = InsightsService(session)

    assert insights.summary(hermann.id).total_photos == 1
    assert insights.summary(biscuit.id).total_photos == 1
