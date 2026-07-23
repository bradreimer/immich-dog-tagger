from unittest.mock import Mock
from sqlalchemy.orm import Session

from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.models import Asset
from immich_dog_tagger.status import AssetStatus


def test_downloader_marks_failed_asset_as_error(engine, tmp_path):
    with Session(engine) as session:
        failed_asset = Asset(
            immich_asset_id="failed-asset",
            checksum="checksum1",
            extension=".jpg",
        )

        good_asset = Asset(
            immich_asset_id="good-asset",
            checksum="checksum2",
            extension=".jpg",
        )

        session.add_all(
            [
                failed_asset,
                good_asset,
            ]
        )

        session.commit()

        client = Mock()

        def download_asset(asset_id):
            if asset_id == "failed-asset":
                raise Exception("Asset not found")

            return b"image data"

        client.download_asset.side_effect = download_asset

        downloader = Downloader(
            client,
            session,
            tmp_path,
        )

        count = downloader.download_pending(force=True)

        assert client.download_asset.call_count == 2

        assert count == 1

        session.refresh(failed_asset)
        session.refresh(good_asset)

        assert failed_asset.status == AssetStatus.DOWNLOAD_FAILED
        assert good_asset.status == AssetStatus.DOWNLOADED

        assert (tmp_path / "good-asset.jpg").exists()


def test_download_force_reprocesses_existing_asset(
    engine,
    tmp_path,
):
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )

        session.add(asset)
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                assert asset_id == "abc123"
                return b"image-data"

        downloader = Downloader(
            FakeClient(),
            session,
            tmp_path,
        )

        result = downloader.download_pending(
            force=True,
        )

        assert result == 1

        session.refresh(asset)

        assert asset.status is AssetStatus.DOWNLOADED
        assert asset.cache_path(tmp_path).read_bytes() == b"image-data"


def test_download_skips_non_pending_assets(
    engine,
    tmp_path,
):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )

        session.add(asset)
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                raise AssertionError("should not download")

        downloader = Downloader(
            FakeClient(),
            session,
            tmp_path,
        )

        result = downloader.download_pending()

        assert result == 0
