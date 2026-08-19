from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import Species
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    EmbeddingExample,
    Identity,
    IdentityMerge,
    PetOccurrence,
)

# Merging a well-populated identity rewrites every classification it owns.
# Committing in bounded batches keeps state.db's single write lock available
# to the pipeline instead of holding it for the whole rewrite (issues #104/#107).
MERGE_BATCH_SIZE = 500


@dataclass(frozen=True)
class MergeSummary:
    source_id: int
    source_name: str
    target_id: int
    target_name: str
    species: Species
    classifications_reassigned: int
    examples_reassigned: int
    examples_discarded: int
    occurrences_reassigned: int


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

    def deactivate_dog(self, dog_id: int) -> Identity:
        return self.set_active(dog_id, False)

    def activate_dog(self, dog_id: int) -> Identity:
        return self.set_active(dog_id, True)

    def merge_dogs(
        self,
        source_id: int,
        target_id: int,
        *,
        batch_size: int = MERGE_BATCH_SIZE,
    ) -> MergeSummary:
        """
        Absorb `source_id` into `target_id` (issue #148).

        Every classification attributed to the source and every reference
        example it owns move to the target; the source is left behind as a
        deactivated tombstone rather than deleted, and the merge itself is
        recorded in `identity_merges` so a bulk re-attribution stays
        traceable afterwards.

        Review history is deliberately untouched: `ReviewAction` rows keep
        the identity strings a human actually chose at the time. A merge
        rewrites derived attribution, not the record of who decided what.

        Immich albums reconcile on the next sync rather than here -- the
        source's `SyncedAsset` rows are left alone precisely so
        `SyncService.sync()` sees that membership as stale and removes it
        (the DT-1113 machinery).
        """
        if source_id == target_id:
            raise ValueError("Cannot merge an identity into itself")

        source = self._require_dog(source_id)
        target = self._require_dog(target_id)

        if source.species != target.species:
            # Names are unique per species, not globally (DT-1110): a dog
            # "Max" and a cat "Max" are two legitimately different animals,
            # so a cross-species merge is a mistake, not a coercion.
            raise ValueError(
                f"Cannot merge a {source.species.value} into a "
                f"{target.species.value}: both identities must be the same species"
            )

        species = source.species
        source_name = source.name
        target_name = target.name

        examples_reassigned, examples_discarded = self._merge_examples(
            source.id,
            target.id,
            batch_size=batch_size,
        )

        classifications_reassigned = self._merge_classifications(
            source_name,
            target_name,
            species,
            batch_size=batch_size,
        )

        occurrences_reassigned = self._merge_occurrences(
            source.id,
            target.id,
            batch_size=batch_size,
        )

        source.is_active = False

        self.session.add(
            IdentityMerge(
                source_identity_id=source.id,
                target_identity_id=target.id,
                source_name=source_name,
                target_name=target_name,
                species=species,
                classifications_reassigned=classifications_reassigned,
                examples_reassigned=examples_reassigned,
                examples_discarded=examples_discarded,
                occurrences_reassigned=occurrences_reassigned,
            )
        )

        self.session.commit()

        return MergeSummary(
            source_id=source_id,
            source_name=source_name,
            target_id=target_id,
            target_name=target_name,
            species=species,
            classifications_reassigned=classifications_reassigned,
            examples_reassigned=examples_reassigned,
            examples_discarded=examples_discarded,
            occurrences_reassigned=occurrences_reassigned,
        )

    def _merge_examples(
        self,
        source_id: int,
        target_id: int,
        *,
        batch_size: int,
    ) -> tuple[int, int]:
        """
        Re-file the source's reference examples onto the target, batch by
        batch. A physical crop can only depict one animal, so a source
        example whose crop path the target already holds is discarded rather
        than duplicated -- the same invariant `Learner` maintains.
        """
        target_paths = set(
            self.session.scalars(
                select(EmbeddingExample.crop_path).where(
                    EmbeddingExample.identity_id == target_id
                )
            ).all()
        )

        reassigned = 0
        discarded = 0

        while True:
            batch = self.session.scalars(
                select(EmbeddingExample)
                .where(EmbeddingExample.identity_id == source_id)
                .order_by(EmbeddingExample.id)
                .limit(batch_size)
            ).all()

            if not batch:
                break

            for example in batch:
                if example.crop_path in target_paths:
                    self.session.delete(example)
                    discarded += 1
                    continue

                example.identity_id = target_id
                target_paths.add(example.crop_path)
                reassigned += 1

            self.session.commit()

        return reassigned, discarded

    def _merge_classifications(
        self,
        source_name: str,
        target_name: str,
        species: Species,
        *,
        batch_size: int,
    ) -> int:
        """
        Point every classification naming the source at the target instead.

        `CropClassification.identity` is a bare name, so the rewrite is
        scoped to crops of the merged species -- otherwise merging the dog
        "Max" would also re-attribute the cat "Max"'s photos.
        """
        classification_ids = self.session.scalars(
            select(CropClassification.id)
            .join(Crop, CropClassification.crop_id == Crop.id)
            .where(
                CropClassification.identity == source_name,
                Crop.species == species,
            )
            .order_by(CropClassification.id)
        ).all()

        for start in range(0, len(classification_ids), batch_size):
            chunk = classification_ids[start : start + batch_size]

            self.session.execute(
                update(CropClassification)
                .where(CropClassification.id.in_(chunk))
                .values(identity=target_name),
                execution_options={"synchronize_session": False},
            )

            self.session.commit()

        return len(classification_ids)

    def _merge_occurrences(
        self,
        source_id: int,
        target_id: int,
        *,
        batch_size: int,
    ) -> int:
        """
        Re-point the source's PetOccurrence rows at the target so insights
        follow the merge. These are derived facts (ADR-004) -- rebuildable
        from classifications -- but rewriting them here keeps the merge a
        single settled step instead of one that needs a rebuild to look
        finished.
        """
        occurrence_ids = self.session.scalars(
            select(PetOccurrence.id)
            .where(PetOccurrence.identity_id == source_id)
            .order_by(PetOccurrence.id)
        ).all()

        for start in range(0, len(occurrence_ids), batch_size):
            chunk = occurrence_ids[start : start + batch_size]

            self.session.execute(
                update(PetOccurrence)
                .where(PetOccurrence.id.in_(chunk))
                .values(identity_id=target_id),
                execution_options={"synchronize_session": False},
            )

            self.session.commit()

        return len(occurrence_ids)

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
