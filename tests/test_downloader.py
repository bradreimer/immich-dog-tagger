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

        count = downloader.download_pending()

        assert count == 1

        session.refresh(failed_asset)
        session.refresh(good_asset)

        assert failed_asset.status == AssetStatus.DOWNLOAD_FAILED
        assert good_asset.status == AssetStatus.DOWNLOADED

        assert (tmp_path / "good-asset.jpg").exists()
