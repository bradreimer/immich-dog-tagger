from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
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
    confidence: float = 0.9,
    source: ClassificationSources = ClassificationSources.AUTO,
    detection_confidence: float = 0.9,
) -> int:
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
        asset_id=asset.id,
        label="dog",
        confidence=detection_confidence,
        x1=0,
        y1=0,
        x2=1,
        y2=1,
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
        confidence=confidence,
        source=source,
    )
    session.add(classification)
    session.commit()

    service.sync_classification(classification)
    session.commit()

    return asset.id


def _add_occurrence_to_asset(
    session: Session,
    service: PetOccurrenceService,
    *,
    asset_id: int,
    identity_name: str,
    confidence: float = 0.9,
    source: ClassificationSources = ClassificationSources.AUTO,
) -> None:
    detection = Detection(
        asset_id=asset_id, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
    )
    session.add(detection)
    session.flush()

    crop = Crop(
        detection_id=detection.id,
        path=f"{asset_id}-{identity_name}.jpg",
        species=Species.DOG,
    )
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=identity_name,
        confidence=confidence,
        source=source,
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

    assert summary.identity_species == Species.DOG
    assert summary.total_photos == 0
    assert summary.first_seen is None
    assert summary.last_seen is None
    assert not hasattr(summary, "top_place")
    assert not hasattr(summary, "top_person")
    assert summary.favorite_photo_count == 0


def test_summary_computes_counts(session):
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


def test_top_photos_raises_for_missing_identity(session):
    with pytest.raises(IdentityNotFoundError):
        InsightsService(session).top_photos(999)


def test_top_photos_empty_for_identity_with_no_occurrences(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    assert InsightsService(session).top_photos(identity.id) == []


def test_top_photos_orders_by_detection_confidence_descending(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    for immich_asset_id, detection_confidence in [
        ("low", 0.5),
        ("high", 0.95),
        ("mid", 0.7),
    ]:
        _add_occurrence(
            session,
            service,
            identity_name="Hermann",
            immich_asset_id=immich_asset_id,
            detection_confidence=detection_confidence,
        )

    top_photos = InsightsService(session).top_photos(identity.id)

    assert [photo.immich_asset_id for photo in top_photos] == ["high", "mid", "low"]
    assert [photo.clarity for photo in top_photos] == [0.95, 0.7, 0.5]
    assert all(photo.crop_id is not None for photo in top_photos)


def test_top_photos_includes_review_and_manual_sources(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="auto-mid",
        detection_confidence=0.7,
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="reviewed-high",
        source=ClassificationSources.REVIEW,
        detection_confidence=0.9,
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="manual-low",
        source=ClassificationSources.MANUAL,
        detection_confidence=0.4,
    )

    top_photos = InsightsService(session).top_photos(identity.id)

    assert [photo.immich_asset_id for photo in top_photos] == [
        "reviewed-high",
        "auto-mid",
        "manual-low",
    ]


def test_top_photos_ranks_entirely_reviewed_occurrences(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="reviewed",
        source=ClassificationSources.REVIEW,
        detection_confidence=0.8,
    )

    top_photos = InsightsService(session).top_photos(identity.id)

    assert [photo.immich_asset_id for photo in top_photos] == ["reviewed"]


def test_top_photos_respects_limit(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    for i in range(15):
        _add_occurrence(
            session, service, identity_name="Hermann", immich_asset_id=f"a{i}"
        )

    top_photos = InsightsService(session).top_photos(identity.id, limit=10)

    assert len(top_photos) == 10


def test_top_photos_skips_dangling_occurrence_instead_of_crashing(session):
    # Regression coverage for issue #279: a PetOccurrence whose
    # crop_classification_id no longer resolves (e.g. a database that
    # predates the cascading delete fix) must not 500 the endpoint --
    # occurrence.classification loads as None via the LEFT OUTER JOIN in
    # _occurrences(), and top_photos() should skip it rather than crash on
    # occurrence.classification.crop_id.
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(
        session, service, identity_name="Hermann", immich_asset_id="ok", confidence=0.5
    )
    dangling_asset_id = _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="dangling",
        confidence=0.99,
    )

    dangling_occurrence = session.scalars(
        select(PetOccurrence).where(PetOccurrence.asset_id == dangling_asset_id)
    ).one()
    dangling_classification_id = dangling_occurrence.crop_classification_id

    # Raw SQL, not session.delete(), deliberately bypasses the ORM
    # relationship (and its delete-orphan cascade) to reproduce the
    # dangling row a pre-fix database could accumulate.
    session.execute(
        text("DELETE FROM crop_classifications WHERE id = :id"),
        {"id": dangling_classification_id},
    )
    session.commit()
    session.expire_all()

    top_photos = InsightsService(session).top_photos(identity.id)

    assert [photo.immich_asset_id for photo in top_photos] == ["ok"]


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


def test_most_active_month_provider(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a1",
        captured_at=datetime(2023, 3, 1, tzinfo=UTC),
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a2",
        captured_at=datetime(2023, 3, 15, tzinfo=UTC),
    )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a3",
        captured_at=datetime(2023, 6, 1, tzinfo=UTC),
    )

    cards = InsightsService(session).cards(identity.id)
    card = next(c for c in cards if c.slug == "most-active-month")

    assert card.value == "March 2023"
    assert card.subtext == "2 photo(s)"


def test_most_active_month_absent_without_captured_at(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)
    _add_occurrence(session, service, identity_name="Hermann", immich_asset_id="a1")

    cards = InsightsService(session).cards(identity.id)
    assert "most-active-month" not in {c.slug for c in cards}


def test_longest_streak_provider(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)

    for i in range(5):
        _add_occurrence(
            session,
            service,
            identity_name="Hermann",
            immich_asset_id=f"streak-{i}",
            captured_at=datetime(2023, 1, 1, tzinfo=UTC) + timedelta(days=i),
        )
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="gap",
        captured_at=datetime(2023, 2, 1, tzinfo=UTC),
    )

    cards = InsightsService(session).cards(identity.id)
    card = next(c for c in cards if c.slug == "longest-streak")

    assert card.value == "5 days"


def test_longest_streak_absent_for_single_day(session):
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
    )

    cards = InsightsService(session).cards(identity.id)
    assert "longest-streak" not in {c.slug for c in cards}


def test_best_friend_provider(session):
    hermann = Identity(name="Hermann", species=Species.DOG)
    biscuit = Identity(name="Biscuit", species=Species.DOG)
    session.add_all([hermann, biscuit])
    session.commit()

    service = PetOccurrenceService(session)

    for i in range(3):
        asset_id = _add_occurrence(
            session, service, identity_name="Hermann", immich_asset_id=f"shared-{i}"
        )
        _add_occurrence_to_asset(
            session, service, asset_id=asset_id, identity_name="Biscuit"
        )

    # A solo photo of Hermann alone shouldn't count toward any co-occurrence.
    _add_occurrence(session, service, identity_name="Hermann", immich_asset_id="solo")

    cards = InsightsService(session).cards(hermann.id)
    card = next(c for c in cards if c.slug == "best-friend")

    assert card.value == "Biscuit"
    assert card.subtext == "3 photo(s) together"


def test_best_friend_absent_without_co_occurrence(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)
    _add_occurrence(session, service, identity_name="Hermann", immich_asset_id="solo")

    cards = InsightsService(session).cards(identity.id)
    assert "best-friend" not in {c.slug for c in cards}


def test_year_over_year_provider(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)
    current_year = datetime.now(UTC).year

    for i in range(3):
        _add_occurrence(
            session,
            service,
            identity_name="Hermann",
            immich_asset_id=f"last-{i}",
            captured_at=datetime(current_year - 1, 5, 1, tzinfo=UTC),
        )
    for i in range(5):
        _add_occurrence(
            session,
            service,
            identity_name="Hermann",
            immich_asset_id=f"this-{i}",
            captured_at=datetime(current_year, 2, 1, tzinfo=UTC),
        )

    cards = InsightsService(session).cards(identity.id)
    card = next(c for c in cards if c.slug == "year-over-year")

    assert card.value == "+2 photo(s) vs. last year"
    assert card.subtext == "5 this year, 3 last year"


def test_year_over_year_absent_without_prior_year_data(session):
    identity = Identity(name="Hermann", species=Species.DOG)
    session.add(identity)
    session.commit()

    service = PetOccurrenceService(session)
    current_year = datetime.now(UTC).year
    _add_occurrence(
        session,
        service,
        identity_name="Hermann",
        immich_asset_id="a1",
        captured_at=datetime(current_year, 1, 1, tzinfo=UTC),
    )

    cards = InsightsService(session).cards(identity.id)
    assert "year-over-year" not in {c.slug for c in cards}
