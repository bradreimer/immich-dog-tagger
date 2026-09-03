from sqlalchemy.orm import Session

from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection
from immich_dog_tagger.services.job_execution import _sync_handler


class RecordingProgress:
    def __init__(self):
        self.messages: list[str] = []

    def set(self, current=None, total=None, message=None):
        if message is not None:
            self.messages.append(message)

    def message(self, value):
        self.messages.append(value)


class FakeImmichClient:
    def __init__(self):
        self.albums: list[dict] = []
        self.tags: list[dict] = []

    def list_albums(self):
        return self.albums

    def create_album(self, name):
        album = {"id": f"album-{len(self.albums) + 1}", "albumName": name}
        self.albums.append(album)
        return album["id"]

    def add_assets_to_album(self, album_id, asset_ids):
        pass

    def remove_assets_from_album(self, album_id, asset_ids):
        pass

    def list_tags(self):
        return self.tags

    def create_tag(self, name):
        tag = {"id": f"tag-{len(self.tags) + 1}", "name": name}
        self.tags.append(tag)
        return tag["id"]

    def tag_assets(self, tag_id, asset_ids):
        pass

    def untag_assets(self, tag_id, asset_ids):
        pass


def _add_classification(session, *, asset_id, identity, confidence):
    asset = Asset(immich_asset_id=asset_id, checksum="c", extension=".jpg")
    detection = Detection(
        asset=asset, label="dog", confidence=1.0, x1=0, y1=0, x2=10, y2=10
    )
    crop = Crop(detection=detection, path=f"{asset_id}.jpg")
    session.add(CropClassification(crop=crop, identity=identity, confidence=confidence))


def test_sync_handler_reports_skipped_classifications_in_progress_message(
    engine, monkeypatch
):
    """Issue #11: the sync job's own status message must explain a
    lower-than-expected result, not just say "sync completed"."""
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution._create_client",
        lambda config: FakeImmichClient(),
    )

    with Session(engine) as session:
        _add_classification(session, asset_id="good", identity="Fibs", confidence=1.0)
        _add_classification(
            session, asset_id="low-conf", identity="Cooper", confidence=0.5
        )
        session.commit()

        handler = _sync_handler(session, config=None, options={})
        progress = RecordingProgress()
        result = handler(progress)

    assert result["identities"] == 1
    assert result["skipped_low_confidence"] == 1
    assert result["skipped_unknown"] == 0
    assert result["skipped_missing_asset"] == 0

    final_message = progress.messages[-1]
    assert "Synchronized 1 identities" in final_message
    assert "skipped 1 classification" in final_message
    assert "1 below confidence threshold" in final_message


def test_sync_handler_message_has_no_skip_clause_when_nothing_skipped(
    engine, monkeypatch
):
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution._create_client",
        lambda config: FakeImmichClient(),
    )

    with Session(engine) as session:
        _add_classification(session, asset_id="good", identity="Fibs", confidence=1.0)
        session.commit()

        handler = _sync_handler(session, config=None, options={})
        progress = RecordingProgress()
        handler(progress)

    final_message = progress.messages[-1]
    assert "skipped" not in final_message
