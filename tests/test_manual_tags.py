"""
Rescuing a photo whose pet the detector missed (issue #147).
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    Detection,
    Identity,
    ManualAssetTag,
)
from immich_dog_tagger.services.manual_tags import ManualTagService


def _seed_pet(session: Session, name="Fibs", species=Species.DOG) -> Identity:
    pet = Identity(name=name, species=species, is_active=True)
    session.add(pet)
    session.flush()
    return pet


def _seed_asset(
    session: Session,
    *,
    immich_asset_id="asset-1",
    status=AssetStatus.DETECTED,
    with_crop=False,
    captured_at=None,
) -> Asset:
    asset = Asset(
        immich_asset_id=immich_asset_id,
        extension=".jpg",
        status=status,
        captured_at=captured_at
        or datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    )

    session.add(asset)
    session.flush()

    if with_crop:
        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=1,
            y2=1,
        )
        session.add(Crop(detection=detection, path="crop.jpg", species=Species.DOG))

    session.commit()

    return asset


def test_undetected_assets_lists_only_photos_that_produced_no_crop(engine):
    with Session(engine) as session:
        _seed_pet(session)
        missed = _seed_asset(session, immich_asset_id="missed", with_crop=False)
        _seed_asset(session, immich_asset_id="found", with_crop=True)

        page = ManualTagService(session).undetected_assets()

        assert [item.immich_asset_id for item in page.items] == ["missed"]
        assert page.total == 1
        assert page.items[0].asset_id == missed.id


def test_undetected_assets_excludes_photos_detection_has_not_reached(engine):
    """
    A photo still queued has not been *missed*, it simply has not been
    looked at -- the same distinction #146's coverage denominator draws.
    """
    with Session(engine) as session:
        _seed_pet(session)
        _seed_asset(session, immich_asset_id="queued", status=AssetStatus.PENDING)
        _seed_asset(
            session, immich_asset_id="downloaded", status=AssetStatus.DOWNLOADED
        )
        _seed_asset(
            session, immich_asset_id="failed", status=AssetStatus.DETECTION_FAILED
        )
        _seed_asset(session, immich_asset_id="done", status=AssetStatus.DETECTED)

        page = ManualTagService(session).undetected_assets()

        assert [item.immich_asset_id for item in page.items] == ["done"]


def test_tagging_records_the_pet(engine):
    with Session(engine) as session:
        _seed_pet(session)
        asset = _seed_asset(session)

        service = ManualTagService(session)
        service.tag(asset.id, "Fibs", Species.DOG)

        tags = session.query(ManualAssetTag).all()

        assert len(tags) == 1
        assert tags[0].identity == "Fibs"
        assert tags[0].species == Species.DOG


def test_tagging_twice_records_one_fact(engine):
    """
    Idempotent, so a repeated request cannot multiply album membership.
    """
    with Session(engine) as session:
        _seed_pet(session)
        asset = _seed_asset(session)

        service = ManualTagService(session)
        service.tag(asset.id, "Fibs", Species.DOG)
        service.tag(asset.id, "Fibs", Species.DOG)

        assert session.query(ManualAssetTag).count() == 1


def test_a_photo_can_hold_more_than_one_pet(engine):
    with Session(engine) as session:
        _seed_pet(session, "Fibs")
        _seed_pet(session, "Hermann")
        asset = _seed_asset(session)

        service = ManualTagService(session)
        service.tag(asset.id, "Fibs", Species.DOG)
        service.tag(asset.id, "Hermann", Species.DOG)

        assert [tag.identity for tag in service.tags_for(asset.id)] == [
            "Fibs",
            "Hermann",
        ]


def test_tagging_an_unknown_pet_is_refused(engine):
    with Session(engine) as session:
        _seed_pet(session)
        asset = _seed_asset(session)

        try:
            ManualTagService(session).tag(asset.id, "Nobody", Species.DOG)
        except ValueError:
            pass
        else:
            raise AssertionError("expected a ValueError")

        assert session.query(ManualAssetTag).count() == 0


def test_tagging_the_wrong_species_name_is_refused(engine):
    with Session(engine) as session:
        _seed_pet(session, "Fibs", Species.DOG)
        asset = _seed_asset(session)

        try:
            ManualTagService(session).tag(asset.id, "Fibs", Species.CAT)
        except ValueError:
            pass
        else:
            raise AssertionError("expected a ValueError")


def test_untagging_removes_it(engine):
    with Session(engine) as session:
        _seed_pet(session)
        asset = _seed_asset(session)

        service = ManualTagService(session)
        service.tag(asset.id, "Fibs", Species.DOG)

        assert service.untag(asset.id, "Fibs", Species.DOG) is True
        assert session.query(ManualAssetTag).count() == 0

        # Removing what is not there is a no-op, not an error.
        assert service.untag(asset.id, "Fibs", Species.DOG) is False


def test_undetected_assets_reports_existing_tags(engine):
    with Session(engine) as session:
        _seed_pet(session)
        asset = _seed_asset(session)

        service = ManualTagService(session)
        service.tag(asset.id, "Fibs", Species.DOG)

        page = service.undetected_assets()

        assert page.items[0].identities == ["Fibs"]


def test_undetected_assets_can_filter_to_untagged_photos(engine):
    with Session(engine) as session:
        _seed_pet(session)
        tagged = _seed_asset(session, immich_asset_id="tagged")
        _seed_asset(session, immich_asset_id="untouched")

        service = ManualTagService(session)
        service.tag(tagged.id, "Fibs", Species.DOG)

        untouched = service.undetected_assets(tagged=False)
        assert [item.immich_asset_id for item in untouched.items] == ["untouched"]

        rescued = service.undetected_assets(tagged=True)
        assert [item.immich_asset_id for item in rescued.items] == ["tagged"]


def test_undetected_assets_paginate_newest_first(engine):
    with Session(engine) as session:
        _seed_pet(session)

        for index in range(3):
            _seed_asset(
                session,
                immich_asset_id=f"asset-{index}",
                captured_at=datetime(2026, 1, index + 1, tzinfo=UTC).replace(
                    tzinfo=None
                ),
            )

        service = ManualTagService(session)

        first = service.undetected_assets(limit=2, offset=0)
        second = service.undetected_assets(limit=2, offset=2)

        assert first.total == 3
        assert [item.immich_asset_id for item in first.items] == [
            "asset-2",
            "asset-1",
        ]
        assert [item.immich_asset_id for item in second.items] == ["asset-0"]


def test_a_manual_tag_never_becomes_a_reference_example(engine):
    """
    There is no crop and no embedding behind a manual tag, so nothing about
    it may reach the learned reference set -- the guarantee that keeps the
    classifier honest about what it has actually seen.
    """
    from immich_dog_tagger.models import EmbeddingExample

    with Session(engine) as session:
        _seed_pet(session)
        asset = _seed_asset(session)

        ManualTagService(session).tag(asset.id, "Fibs", Species.DOG)

        assert session.query(EmbeddingExample).count() == 0
