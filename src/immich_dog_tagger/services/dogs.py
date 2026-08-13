from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import Species
from immich_dog_tagger.models import Identity


class DogService:
    def __init__(self, session: Session):
        self.session = session

    def list_dogs(self, *, include_inactive: bool = True) -> list[Identity]:
        query = select(Identity).order_by(
            Identity.species.asc(), Identity.is_active.desc(), Identity.name.asc()
        )

        if not include_inactive:
            query = query.where(Identity.is_active.is_(True))

        return self.session.scalars(query).all()

    def get_dog(self, dog_id: int) -> Identity | None:
        return self.session.get(Identity, dog_id)

    def create_dog(self, name: str, species: Species = Species.DOG) -> Identity:
        name = self._normalize_name(name)
        self._ensure_name_available(name, species)

        dog = Identity(name=name, species=species, is_active=True)
        self.session.add(dog)
        self.session.commit()
        self.session.refresh(dog)
        return dog

    def rename_dog(self, dog_id: int, name: str) -> Identity:
        dog = self._require_dog(dog_id)
        name = self._normalize_name(name)
        self._ensure_name_available(name, dog.species, exclude_id=dog_id)

        dog.name = name
        self.session.commit()
        self.session.refresh(dog)
        return dog

    def set_active(self, dog_id: int, active: bool) -> Identity:
        dog = self._require_dog(dog_id)
        dog.is_active = active
        self.session.commit()
        self.session.refresh(dog)
        return dog

    def set_active_range(
        self,
        dog_id: int,
        active_from: datetime | None,
        active_until: datetime | None,
    ) -> Identity:
        """
        DT-1114: an optional owner-set date range the classifier uses to
        flag (never silently exclude) a candidate match whose photo was
        taken outside it. Deliberately a separate method from rename_dog,
        not folded into it -- rename's contract stays name-only.
        """
        if (
            active_from is not None
            and active_until is not None
            and active_from > active_until
        ):
            raise ValueError("active_from must not be after active_until")

        dog = self._require_dog(dog_id)
        dog.active_from = active_from
        dog.active_until = active_until
        self.session.commit()
        self.session.refresh(dog)
        return dog

    def deactivate_dog(self, dog_id: int) -> Identity:
        return self.set_active(dog_id, False)

    def activate_dog(self, dog_id: int) -> Identity:
        return self.set_active(dog_id, True)

    def _require_dog(self, dog_id: int) -> Identity:
        dog = self.get_dog(dog_id)

        if dog is None:
            raise ValueError(f"Dog {dog_id} not found")

        return dog

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()

        if not normalized:
            raise ValueError("Dog name cannot be empty")

        if normalized.casefold() == "unknown":
            raise ValueError("Unknown is reserved")

        return normalized

    def _ensure_name_available(
        self,
        name: str,
        species: Species,
        *,
        exclude_id: int | None = None,
    ) -> None:
        # Names are unique per species (DT-1110), not globally -- a dog
        # "Max" and a cat "Max" are different identities.
        query = select(Identity).where(
            Identity.name == name,
            Identity.species == species,
        )

        if exclude_id is not None:
            query = query.where(Identity.id != exclude_id)

        if self.session.scalar(query) is not None:
            raise ValueError(f"{species.value.capitalize()} already exists: {name}")
