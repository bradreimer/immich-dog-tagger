from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import Identity


class DogService:
    def __init__(self, session: Session):
        self.session = session

    def list_dogs(self, *, include_inactive: bool = True) -> list[Identity]:
        query = select(Identity).order_by(
            Identity.is_active.desc(), Identity.name.asc()
        )

        if not include_inactive:
            query = query.where(Identity.is_active.is_(True))

        return self.session.scalars(query).all()

    def get_dog(self, dog_id: int) -> Identity | None:
        return self.session.get(Identity, dog_id)

    def create_dog(self, name: str) -> Identity:
        name = self._normalize_name(name)
        self._ensure_name_available(name)

        dog = Identity(name=name, is_active=True)
        self.session.add(dog)
        self.session.commit()
        self.session.refresh(dog)
        return dog

    def rename_dog(self, dog_id: int, name: str) -> Identity:
        dog = self._require_dog(dog_id)
        name = self._normalize_name(name)
        self._ensure_name_available(name, exclude_id=dog_id)

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
        self, name: str, *, exclude_id: int | None = None
    ) -> None:
        query = select(Identity).where(Identity.name == name)

        if exclude_id is not None:
            query = query.where(Identity.id != exclude_id)

        if self.session.scalar(query) is not None:
            raise ValueError(f"Dog already exists: {name}")
