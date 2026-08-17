from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.downloader import BATCH_SIZE, Downloader
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


def test_downloader_marks_unexpected_error_as_failed_and_continues(
    engine,
    tmp_path,
):
    # Regression test for issue #99: only ImmichDownloadError was caught
    # per-asset before -- anything else (a disk write failure, an
    # unwrapped network error) used to propagate and abort the whole
    # batch, losing every asset downloaded before it.
    with Session(engine) as session:
        bad_asset = Asset(
            immich_asset_id="bad-asset",
            checksum="checksum1",
            extension=".jpg",
        )

        good_asset = Asset(
            immich_asset_id="good-asset",
            checksum="checksum2",
            extension=".jpg",
        )

        session.add_all([bad_asset, good_asset])
        session.commit()

        client = Mock()

        def download_asset(asset_id):
            if asset_id == "bad-asset":
                raise ValueError("unexpected boom")

            return b"image data"

        client.download_asset.side_effect = download_asset

        downloader = Downloader(client, session, tmp_path)

        count = downloader.download_pending()

        assert client.download_asset.call_count == 2
        assert count == 1

        session.refresh(bad_asset)
        session.refresh(good_asset)

        assert bad_asset.status == AssetStatus.DOWNLOAD_FAILED
        assert good_asset.status == AssetStatus.DOWNLOADED


def test_download_pending_commits_in_batches_of_1000(
    engine,
    tmp_path,
):
    total = BATCH_SIZE + 500

    with Session(engine) as session:
        session.add_all(
            [
                Asset(
                    immich_asset_id=f"asset-{i}",
                    checksum=str(i),
                    extension=".jpg",
                )
                for i in range(total)
            ]
        )
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                return b"data"

        downloader = Downloader(FakeClient(), session, tmp_path)

        commit_calls = []
        original_commit = session.commit

        def counting_commit():
            commit_calls.append(1)
            original_commit()

        session.commit = counting_commit

        count = downloader.download_pending()

        assert count == total
        # One commit at the BATCH_SIZE boundary, one final commit for the
        # remaining 500.
        assert len(commit_calls) == 2


def test_download_pending_batch_commit_failure_leaves_prior_batch_committed(
    engine,
    tmp_path,
):
    # Regression test for issue #99: if persisting a batch itself fails
    # (DB error), only the still-uncommitted batch should be lost --
    # already-committed batches must survive.
    total = BATCH_SIZE + 500

    with Session(engine) as session:
        session.add_all(
            [
                Asset(
                    immich_asset_id=f"asset-{i}",
                    checksum=str(i),
                    extension=".jpg",
                )
                for i in range(total)
            ]
        )
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                return b"data"

        downloader = Downloader(FakeClient(), session, tmp_path)

        original_commit = session.commit
        calls = {"n": 0}

        def flaky_commit():
            calls["n"] += 1

            if calls["n"] == 1:
                original_commit()
                return

            raise RuntimeError("db unavailable")

        session.commit = flaky_commit

        with pytest.raises(RuntimeError, match="db unavailable"):
            downloader.download_pending()

    with Session(engine) as verify_session:
        downloaded = (
            verify_session.query(Asset).filter_by(status=AssetStatus.DOWNLOADED).count()
        )

        assert downloaded == BATCH_SIZE


def test_download_pending_honors_should_cancel_and_keeps_only_committed_batches(
    engine,
    tmp_path,
):
    # Issue #111: cancellation reuses the same commit checkpoint as a
    # crash-safety failure would.
    total = 2 * BATCH_SIZE
    cancel_at = BATCH_SIZE + max(1, BATCH_SIZE // 2)

    with Session(engine) as session:
        session.add_all(
            [
                Asset(
                    immich_asset_id=f"asset-{i}",
                    checksum=str(i),
                    extension=".jpg",
                )
                for i in range(total)
            ]
        )
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                return b"data"

        downloader = Downloader(FakeClient(), session, tmp_path)

        calls = {"count": 0}

        def should_cancel():
            calls["count"] += 1
            return calls["count"] > cancel_at

        downloaded = downloader.download_pending(should_cancel=should_cancel)

        assert downloaded == BATCH_SIZE

    with Session(engine) as verify_session:
        count = (
            verify_session.query(Asset).filter_by(status=AssetStatus.DOWNLOADED).count()
        )

        assert count == BATCH_SIZE


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


def test_download_pending_retries_previously_failed_asset(
    engine,
    tmp_path,
):
    # A DOWNLOAD_FAILED asset (e.g. from a timeout) must be retried by a
    # plain, non-force download -- otherwise it's stuck forever unless
    # someone remembers to pass --force, which redownloads everything.
    with Session(engine) as session:
        failed = Asset(
            immich_asset_id="previously-failed",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOAD_FAILED,
        )

        session.add(failed)
        session.commit()

        class FakeClient:
            def download_asset(self, asset_id):
                return b"image data"

        downloader = Downloader(
            FakeClient(),
            session,
            tmp_path,
        )

        result = downloader.download_pending()

        assert result == 1

        session.refresh(failed)

        assert failed.status == AssetStatus.DOWNLOADED
        assert (tmp_path / "previously-failed.jpg").exists()


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
