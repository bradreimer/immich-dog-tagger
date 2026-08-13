from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.models import Identity
from immich_dog_tagger.services.dogs import DogService


def test_fresh_install_starts_without_dogs(tmp_path):
    engine = create_database(tmp_path)

    with Session(engine) as session:
        dogs = DogService(session).list_dogs()

    assert dogs == []


def test_dog_service_creates_renames_and_deactivates(engine):
    with Session(engine) as session:
        service = DogService(session)

        dog = service.create_dog("Fibs")
        assert dog.name == "Fibs"

        renamed = service.rename_dog(dog.id, "Fibs Prime")
        deactivated = service.deactivate_dog(dog.id)
        assert deactivated.is_active is False

        reactivated = service.activate_dog(dog.id)

    assert renamed.name == "Fibs Prime"
    assert reactivated.is_active is True

    with Session(engine) as session:
        persisted = DogService(session).get_dog(dog.id)

    assert persisted is not None
    assert persisted.name == "Fibs Prime"
    assert persisted.is_active is True


def test_dog_service_rejects_reserved_and_blank_names(engine):
    with Session(engine) as session:
        service = DogService(session)

        try:
            service.create_dog("   ")
        except ValueError as exc:
            assert "empty" in str(exc)
        else:
            raise AssertionError("Expected blank dog name to be rejected")

        try:
            service.create_dog("Unknown")
        except ValueError as exc:
            assert "reserved" in str(exc)
        else:
            raise AssertionError("Expected reserved dog name to be rejected")


def test_dog_service_sets_active_range(engine):
    with Session(engine) as session:
        service = DogService(session)

        dog = service.create_dog("Fibs")
        assert dog.active_from is None
        assert dog.active_until is None

        active_from = datetime(2015, 1, 1, tzinfo=UTC)
        active_until = datetime(2019, 12, 31, tzinfo=UTC)

        updated = service.set_active_range(dog.id, active_from, active_until)

        assert updated.active_from == active_from.replace(tzinfo=None)
        assert updated.active_until == active_until.replace(tzinfo=None)

    with Session(engine) as session:
        persisted = DogService(session).get_dog(dog.id)

    assert persisted.active_from == active_from.replace(tzinfo=None)
    assert persisted.active_until == active_until.replace(tzinfo=None)


def test_dog_service_set_active_range_accepts_one_bound_only(engine):
    with Session(engine) as session:
        service = DogService(session)
        dog = service.create_dog("Fibs")

        active_from = datetime(2019, 1, 1, tzinfo=UTC)
        updated = service.set_active_range(dog.id, active_from, None)

        assert updated.active_from == active_from.replace(tzinfo=None)
        assert updated.active_until is None


def test_dog_service_rejects_active_from_after_active_until(engine):
    with Session(engine) as session:
        service = DogService(session)
        dog = service.create_dog("Fibs")

        with pytest.raises(ValueError, match="active_from"):
            service.set_active_range(
                dog.id,
                datetime(2020, 1, 1, tzinfo=UTC),
                datetime(2019, 1, 1, tzinfo=UTC),
            )


def test_dog_service_persists_identity_is_active(engine):
    with Session(engine) as session:
        dog = Identity(name="Henri")
        session.add(dog)
        session.commit()

        dog_id = dog.id

    with Session(engine) as session:
        result = session.get(Identity, dog_id)

    assert result is not None
    assert result.is_active is True
