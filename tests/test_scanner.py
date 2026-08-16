import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.immich import ImmichAsset, ImmichPerson
from immich_dog_tagger.models import Asset
from immich_dog_tagger.scanner import BATCH_SIZE, Scanner


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


def test_scan_populates_immich_metadata_on_new_asset(engine):
    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id="abc123",
                    filename="dog.jpg",
                    checksum="xyz",
                    city="Seattle",
                    country="United States",
                    is_favorite=True,
                    people=(ImmichPerson(id="p1", name="Brad"),),
                )
            ]

    with Session(engine) as session:
        Scanner(FakeClient(), session).scan()

        asset = session.scalar(select(Asset))

        assert asset.city == "Seattle"
        assert asset.country == "United States"
        assert asset.is_favorite is True
        assert asset.people == [{"id": "p1", "name": "Brad"}]
        assert asset.metadata_synced_at is not None


def test_scan_refreshes_immich_metadata_on_existing_asset(engine):
    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id="abc123",
                    filename="dog.jpg",
                    checksum="xyz",
                    is_favorite=True,
                    people=(ImmichPerson(id="p1", name="Brad"),),
                )
            ]

    with Session(engine) as session:
        session.add(
            Asset(
                immich_asset_id="abc123",
                checksum="xyz",
                extension=".jpg",
                is_favorite=False,
            )
        )
        session.commit()

        # Same checksum, so this isn't a "new asset" -- but the favorite
        # flag/recognized people can change in Immich without the photo
        # file itself changing, so metadata still refreshes.
        Scanner(FakeClient(), session).scan()

        asset = session.scalar(select(Asset))

        assert asset.is_favorite is True
        assert asset.people == [{"id": "p1", "name": "Brad"}]


def test_scan_force_resets_status_when_checksum_changes(
    engine,
):
    class ChangedAssetClient:
        def list_assets(self):
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


def test_scan_commits_in_batches_of_1000(engine):
    total = BATCH_SIZE + 500

    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id=str(i),
                    filename=f"{i}.jpg",
                    checksum=str(i),
                )
                for i in range(total)
            ]

    with Session(engine) as session:
        scanner = Scanner(FakeClient(), session)

        commit_calls = []
        original_commit = session.commit

        def counting_commit():
            commit_calls.append(1)
            original_commit()

        session.commit = counting_commit

        count = scanner.scan()

        assert count == total
        # One commit at the BATCH_SIZE boundary, one final commit for the
        # remaining 500 -- proves the loop doesn't hold everything for a
        # single commit at the end.
        assert len(commit_calls) == 2
        assert session.query(Asset).count() == total


def test_scan_failure_leaves_only_prior_batches_committed(engine):
    # Regression test for issue #99: a failure partway through a run must
    # not discard batches already committed, so a retry only has to redo
    # what wasn't durable yet.
    total = BATCH_SIZE + 500
    fail_at = BATCH_SIZE + 200

    class FakeClient:
        def list_assets(self):
            return [
                ImmichAsset(
                    id=str(i),
                    filename=f"{i}.jpg",
                    checksum=str(i),
                )
                for i in range(total)
            ]

    class FlakyScanner(Scanner):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._calls = 0

        def _process_asset(self, immich_asset, force):
            self._calls += 1

            if self._calls == fail_at:
                raise RuntimeError("simulated failure")

            return super()._process_asset(immich_asset, force)

    with Session(engine) as session:
        scanner = FlakyScanner(FakeClient(), session)

        with pytest.raises(RuntimeError, match="simulated failure"):
            scanner.scan()

    with Session(engine) as verify_session:
        # Only the first full batch (1000) was committed; the failure at
        # 1200 happened inside the still-uncommitted second batch, which
        # was rolled back in full.
        assert verify_session.query(Asset).count() == BATCH_SIZE
