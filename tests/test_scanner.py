from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.immich import ImmichAsset
from immich_dog_tagger.models import Asset
from immich_dog_tagger.scanner import Scanner
from immich_dog_tagger.status import AssetStatus


class FakeImmich:
    def list_assets(self):
        return [
            ImmichAsset(
                id="abc123",
                filename="dog.jpg",
                checksum="xyz",
            )
        ]


def test_scanner_is_incremental(engine):
    with Session(engine) as session:
        scanner = Scanner(
            FakeImmich(),
            session,
        )

        assert scanner.scan() == 1
        assert scanner.scan() == 0

        asset = session.scalar(select(Asset))

        assert asset is not None
        assert asset.immich_asset_id == "abc123"
        assert asset.checksum == "xyz"


def test_scan_limit(engine):
    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id="1",
                    filename="a.jpg",
                    checksum="aaa",
                ),
                ImmichAsset(
                    id="2",
                    filename="b.jpg",
                    checksum="bbb",
                ),
                ImmichAsset(
                    id="3",
                    filename="c.jpg",
                    checksum="ccc",
                ),
            ]

    with Session(engine) as session:
        scanner = Scanner(
            FakeClient(),
            session,
        )

        count = scanner.scan(limit=2)

        assert count == 2
        assert session.query(Asset).count() == 2


def test_scan_force_updates_existing(engine):
    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id="asset-1",
                    filename="dog.jpg",
                    checksum="new-checksum",
                )
            ]

    with Session(engine) as session:
        session.add(
            Asset(
                immich_asset_id="asset-1",
                checksum="old-checksum",
                extension=".png",
            )
        )
        session.commit()

        scanner = Scanner(
            FakeClient(),
            session,
        )

        count = scanner.scan(force=True)

        assert count == 1

        asset = session.query(Asset).filter_by(immich_asset_id="asset-1").one()

        assert asset.checksum == "new-checksum"
        assert asset.status is AssetStatus.PENDING
        assert asset.extension == ".jpg"
        assert session.query(Asset).count() == 1


def test_scan_force_resets_changed_asset(engine):
    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id="asset-1",
                    filename="dog.jpg",
                    checksum="new",
                )
            ]

    with Session(engine) as session:
        session.add(
            Asset(
                immich_asset_id="asset-1",
                checksum="old",
                extension=".jpg",
                status=AssetStatus.CLASSIFIED,
            )
        )
        session.commit()

        Scanner(
            FakeClient(),
            session,
        ).scan(force=True)

        asset = session.query(Asset).one()

        assert asset.checksum == "new"
        assert asset.status is AssetStatus.PENDING


def test_scan_force_preserves_status_when_checksum_unchanged(
    engine,
):
    from sqlalchemy.orm import Session

    from immich_dog_tagger.models import Asset
    from immich_dog_tagger.status import AssetStatus

    class SameAssetClient:
        def list_assets(self):
            from immich_dog_tagger.immich import ImmichAsset

            return [
                ImmichAsset(
                    id="abc123",
                    filename="photo.jpg",
                    checksum="same-checksum",
                )
            ]

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="same-checksum",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )

        session.add(asset)
        session.commit()

        scanner = Scanner(
            SameAssetClient(),
            session,
        )

        result = scanner.scan(
            force=True,
        )

        assert result == 0

        session.refresh(asset)

        assert asset.checksum == "same-checksum"
        assert asset.status is AssetStatus.DETECTED


def test_scan_force_resets_status_when_checksum_changes(
    engine,
):
    from sqlalchemy.orm import Session

    from immich_dog_tagger.models import Asset
    from immich_dog_tagger.status import AssetStatus

    class ChangedAssetClient:
        def list_assets(self):
            from immich_dog_tagger.immich import ImmichAsset

            return [
                ImmichAsset(
                    id="abc123",
                    filename="photo.jpg",
                    checksum="new-checksum",
                )
            ]

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="old-checksum",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )

        session.add(asset)
        session.commit()

        scanner = Scanner(
            ChangedAssetClient(),
            session,
        )

        result = scanner.scan(
            force=True,
        )

        assert result == 1

        session.refresh(asset)

        assert asset.checksum == "new-checksum"
        assert asset.extension == ".jpg"
        assert asset.status is AssetStatus.PENDING
