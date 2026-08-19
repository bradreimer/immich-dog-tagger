"""Merging one identity into another (issue #148)."""

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    IdentityMerge,
    PetOccurrence,
    ReviewAction,
)
from immich_dog_tagger.services.dogs import DogService
from immich_dog_tagger.services.reclassify import ReclassifyService
from immich_dog_tagger.services.sync import SyncService

from .test_reclassify import FakeBatchEmbedder
from .test_sync import FakeAlbums


def _add_example(session, identity, crop_path, vector=(1, 0, 0)):
    example = EmbeddingExample(
        identity_id=identity.id,
        crop_path=crop_path,
        embedding=embedding_to_blob(np.array(vector, dtype=np.float32)),
        source=EmbeddingSources.REVIEW,
    )
    session.add(example)
    session.flush()
    return example


def _add_classification(
    session,
    *,
    identity,
    path,
    species=Species.DOG,
    confidence=0.95,
    source=ClassificationSources.AUTO,
    asset_id=None,
    embedding=None,
):
    detection = None

    if asset_id is not None:
        asset = Asset(
            immich_asset_id=asset_id,
            checksum=asset_id,
            extension=".jpg",
        )
        detection = Detection(
            asset=asset,
            label=species.value,
            confidence=1.0,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )
        session.add(detection)
        session.flush()

    crop = Crop(
        detection_id=detection.id if detection is not None else 1,
        path=path,
        species=species,
    )
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=identity,
        confidence=confidence,
        source=source,
        embedding=embedding_to_blob(np.array(embedding, dtype=np.float32))
        if embedding is not None
        else None,
    )
    session.add(classification)
    session.commit()
    session.refresh(classification)
    return classification


def test_merge_moves_classifications_and_examples_to_the_target(engine):
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        _add_example(session, source, "fibsy-a.jpg")
        _add_example(session, source, "fibsy-b.jpg")
        _add_example(session, target, "fibs-a.jpg")
        session.commit()

        _add_classification(session, identity="Fibsy", path="fibsy-a.jpg")
        _add_classification(session, identity="Fibsy", path="fibsy-b.jpg")
        _add_classification(session, identity="Fibs", path="fibs-a.jpg")

        summary = service.merge_dogs(source.id, target.id)
        target_id = target.id

        assert summary.classifications_reassigned == 2
        assert summary.examples_reassigned == 2
        assert summary.examples_discarded == 0
        assert summary.source_name == "Fibsy"
        assert summary.target_name == "Fibs"

    with Session(engine) as session:
        identities = {
            classification.identity
            for classification in session.scalars(select(CropClassification)).all()
        }
        assert identities == {"Fibs"}

        owners = {
            example.identity_id
            for example in session.scalars(select(EmbeddingExample)).all()
        }
        assert owners == {target_id}


def test_merge_leaves_the_source_as_a_deactivated_tombstone(engine):
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        service.merge_dogs(source.id, target.id)
        source_id, target_id = source.id, target.id

    with Session(engine) as session:
        merged = session.get(Identity, source_id)

        assert merged is not None, "the source is a tombstone, not a deletion"
        assert merged.name == "Fibsy"
        assert merged.is_active is False

        assert session.get(Identity, target_id).is_active is True


def test_merge_records_provenance(engine):
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        _add_example(session, source, "fibsy-a.jpg")
        session.commit()

        _add_classification(session, identity="Fibsy", path="fibsy-a.jpg")

        service.merge_dogs(source.id, target.id)
        source_id, target_id = source.id, target.id

    with Session(engine) as session:
        merges = session.scalars(select(IdentityMerge)).all()

        assert len(merges) == 1

        merge = merges[0]
        assert merge.source_identity_id == source_id
        assert merge.target_identity_id == target_id
        assert merge.source_name == "Fibsy"
        assert merge.target_name == "Fibs"
        assert merge.species is Species.DOG
        assert merge.classifications_reassigned == 1
        assert merge.examples_reassigned == 1
        assert merge.created_at is not None


def test_merge_rejects_a_cross_species_merge(engine):
    with Session(engine) as session:
        service = DogService(session)

        dog = service.create_dog("Max", Species.DOG)
        cat = service.create_dog("Max", Species.CAT)

        _add_classification(session, identity="Max", path="dog-max.jpg")
        _add_classification(
            session,
            identity="Max",
            path="cat-max.jpg",
            species=Species.CAT,
        )

        with pytest.raises(ValueError, match="same species"):
            service.merge_dogs(cat.id, dog.id)

        # Nothing was rewritten on the way to the rejection.
        assert session.get(Identity, cat.id).is_active is True
        assert session.scalars(select(IdentityMerge)).all() == []


def test_merge_only_rewrites_classifications_of_the_merged_species(engine):
    """
    `CropClassification.identity` is a bare name and names are unique per
    species (DT-1110), so merging the dog "Max" must leave the cat "Max"'s
    photos alone.
    """
    with Session(engine) as session:
        service = DogService(session)

        service.create_dog("Max", Species.CAT)
        source = service.create_dog("Max", Species.DOG)
        target = service.create_dog("Maxwell", Species.DOG)

        dog_classification = _add_classification(
            session,
            identity="Max",
            path="dog-max.jpg",
        )
        cat_classification = _add_classification(
            session,
            identity="Max",
            path="cat-max.jpg",
            species=Species.CAT,
        )

        summary = service.merge_dogs(source.id, target.id)

        assert summary.classifications_reassigned == 1

        session.refresh(dog_classification)
        session.refresh(cat_classification)

        assert dog_classification.identity == "Maxwell"
        assert cat_classification.identity == "Max"


def test_merge_discards_an_example_the_target_already_holds(engine):
    """A physical crop depicts one animal, so the duplicate is dropped."""
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        _add_example(session, source, "shared.jpg")
        _add_example(session, source, "only-source.jpg")
        _add_example(session, target, "shared.jpg")
        session.commit()

        summary = service.merge_dogs(source.id, target.id)

        assert summary.examples_reassigned == 1
        assert summary.examples_discarded == 1

    with Session(engine) as session:
        paths = sorted(
            example.crop_path
            for example in session.scalars(select(EmbeddingExample)).all()
        )
        assert paths == ["only-source.jpg", "shared.jpg"]


def test_merge_preserves_review_history(engine):
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        classification = _add_classification(
            session,
            identity="Fibsy",
            path="fibsy-a.jpg",
            source=ClassificationSources.REVIEW,
        )

        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                original_identity=None,
                identity="Fibsy",
            )
        )
        session.commit()

        service.merge_dogs(source.id, target.id)

    with Session(engine) as session:
        actions = session.scalars(select(ReviewAction)).all()

        assert len(actions) == 1
        # The human chose "Fibsy" at the time; a merge re-attributes derived
        # state, it does not rewrite the record of who decided what.
        assert actions[0].identity == "Fibsy"
        assert actions[0].action is ReviewActions.CORRECT

        # ...while the classification itself, and its REVIEW provenance,
        # now belong to the target.
        merged = session.scalars(select(CropClassification)).one()
        assert merged.identity == "Fibs"
        assert merged.source is ClassificationSources.REVIEW


def test_merge_repoints_pet_occurrences(engine):
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        classification = _add_classification(
            session,
            identity="Fibsy",
            path="fibsy-a.jpg",
            asset_id="asset-1",
        )

        session.add(
            PetOccurrence(
                crop_classification_id=classification.id,
                asset_id=classification.crop.detection.asset_id,
                identity_id=source.id,
                confidence=0.95,
                source=ClassificationSources.AUTO,
            )
        )
        session.commit()

        summary = service.merge_dogs(source.id, target.id)

        assert summary.occurrences_reassigned == 1
        target_id = target.id

    with Session(engine) as session:
        occurrence = session.scalars(select(PetOccurrence)).one()
        assert occurrence.identity_id == target_id


def test_merge_rejects_merging_an_identity_into_itself(engine):
    with Session(engine) as session:
        service = DogService(session)
        dog = service.create_dog("Fibs")

        with pytest.raises(ValueError, match="into itself"):
            service.merge_dogs(dog.id, dog.id)


def test_merge_rejects_an_unknown_identity(engine):
    with Session(engine) as session:
        service = DogService(session)
        dog = service.create_dog("Fibs")

        with pytest.raises(ValueError, match="not found"):
            service.merge_dogs(9999, dog.id)

        with pytest.raises(ValueError, match="not found"):
            service.merge_dogs(dog.id, 9999)


def test_merge_commits_in_batches(engine):
    """
    Merging a well-populated identity must not hold one long write
    transaction (the lock-contention class of bug #104/#107 fixed).
    """
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        for index in range(7):
            _add_classification(
                session,
                identity="Fibsy",
                path=f"fibsy-{index}.jpg",
            )
            _add_example(session, source, f"fibsy-{index}.jpg")

        session.commit()

        commits = 0
        original_commit = session.commit

        def counting_commit():
            nonlocal commits
            commits += 1
            original_commit()

        session.commit = counting_commit

        try:
            summary = service.merge_dogs(source.id, target.id, batch_size=2)
        finally:
            session.commit = original_commit

        assert summary.classifications_reassigned == 7
        assert summary.examples_reassigned == 7

        # 4 example batches (the last one empties the source and a fifth
        # query returns nothing), 4 classification batches, and the final
        # commit that deactivates the source and writes the provenance row.
        assert commits >= 8


def test_merged_photos_move_albums_on_the_next_sync(engine):
    """
    FR-10.6: the merge leaves SyncedAsset alone so the DT-1113 stale-membership
    diff removes the source's album membership on the next sync.
    """
    albums = FakeAlbums()

    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        _add_classification(
            session,
            identity="Fibsy",
            path="fibsy-a.jpg",
            asset_id="asset-1",
        )

        SyncService(session, albums).sync()

        assert ("Fibsy", ["asset-1"], Species.DOG) in albums.calls

        service.merge_dogs(source.id, target.id)

        albums.calls.clear()
        SyncService(session, albums).sync()

    assert albums.removals == [("Fibsy", ["asset-1"], Species.DOG)]
    assert albums.calls == [("Fibs", ["asset-1"], Species.DOG)]


def test_reclassify_after_a_merge_does_not_resurrect_the_source(engine):
    with Session(engine) as session:
        service = DogService(session)

        source = service.create_dog("Fibsy")
        target = service.create_dog("Fibs")

        _add_example(session, source, "fibsy-a.jpg", vector=(1, 0, 0))
        session.commit()

        classification = _add_classification(
            session,
            identity="Fibsy",
            path="fibsy-a.jpg",
            embedding=(1, 0, 0),
        )

        service.merge_dogs(source.id, target.id)

        ReclassifyService(session, FakeBatchEmbedder()).reclassify()

        session.refresh(classification)

        assert classification.identity == "Fibs"

    with Session(engine) as session:
        identities = {
            classification.identity
            for classification in session.scalars(select(CropClassification)).all()
        }
        assert "Fibsy" not in identities
