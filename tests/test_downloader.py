from unittest.mock import Mock

from sqlalchemy.orm import Session

from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.immich import ImmichDownloadError
from immich_dog_tagger.models import Asset


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
                raise ImmichDownloadError("Asset not found")

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


def test_download_skips_unsupported_extension(
    engine,
    tmp_path,
):
    # Regression test for issue #93: detect can never process a video/RAW
    # file (see is_supported_image), so downloading it would just waste
    # space for no benefit.
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="video-asset",
            checksum="xyz",
            extension=".mov",
        )

        session.add(asset)
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                raise AssertionError("should not download unsupported types")

        downloader = Downloader(
            FakeClient(),
            session,
            tmp_path,
        )

        result = downloader.download_pending()

        assert result == 0

        session.refresh(asset)

        assert asset.status == AssetStatus.UNSUPPORTED
        assert not (tmp_path / "video-asset.mov").exists()


def test_download_force_cleans_up_previously_downloaded_unsupported_asset(
    engine,
    tmp_path,
):
    # A file downloaded before this check existed sits on disk forever
    # since detect always skips it -- a forced re-check should mark it
    # UNSUPPORTED and reclaim the wasted space.
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="stale-video",
            checksum="xyz",
            extension=".mov",
            status=AssetStatus.DOWNLOADED,
        )

        session.add(asset)
        session.commit()

        stale_file = tmp_path / "stale-video.mov"
        stale_file.write_bytes(b"stale video bytes")

        class FakeClient:
            def download_asset(self, asset_id):
                raise AssertionError("should not download unsupported types")

        downloader = Downloader(
            FakeClient(),
            session,
            tmp_path,
        )

        result = downloader.download_pending(force=True)

        assert result == 0

        session.refresh(asset)

        assert asset.status == AssetStatus.UNSUPPORTED
        assert not stale_file.exists()
