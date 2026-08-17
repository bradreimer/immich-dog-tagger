from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.config import Config
from immich_dog_tagger.services.job_execution import _full_pipeline_handler
from immich_dog_tagger.services.pipeline import BATCH_SIZE


class RecordingProgress:
    def __init__(self):
        self.messages: list[str] = []
        self.sets: list[tuple[int, int | None]] = []

    def message(self, value):
        self.messages.append(value)

    def set(self, current=None, total=None, message=None):
        self.sets.append((current, total))

        if message is not None:
            self.messages.append(message)


class FakeScanner:
    def __init__(self, client, session):
        pass

    def scan(self, limit=None, force=False):
        return BATCH_SIZE + 500


class PoolStage:
    """Shared shape for the download/detect/classify fakes below: each call
    drains a fixed-size pool by min(limit, remaining), so batching behaves
    like the real status-filtered queries it stands in for."""

    def __init__(self, total):
        self.remaining = total

    def _take(self, limit):
        n = min(limit, self.remaining) if limit is not None else self.remaining
        self.remaining -= n
        return n


class FakeDownloader(PoolStage):
    def __init__(self, client, session, cache_dir):
        super().__init__(BATCH_SIZE + 500)

    def download_pending(self, limit=None, force=False):
        return self._take(limit)


class FakeDetectionService(PoolStage):
    def __init__(self, detector, session, cache_dir, crop_writer=None):
        super().__init__(BATCH_SIZE + 500)

    def run(self, limit=None, force=False):
        from immich_dog_tagger.services.detection import DetectionSummary

        n = self._take(limit)
        return DetectionSummary(processed=n, detections=n, dogs=n, cats=0)


class FakeClassificationService(PoolStage):
    def __init__(self, session, embedder, classifier, policy=None):
        super().__init__(BATCH_SIZE + 500)

    def classify(self, mode=None, limit=None, threshold=None):
        from immich_dog_tagger.services.classification import ClassificationSummary

        n = self._take(limit)
        return ClassificationSummary(classified=n, identities={})


def _patch_pipeline_dependencies(monkeypatch):
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution._create_client",
        lambda config: object(),
    )
    monkeypatch.setattr("immich_dog_tagger.services.job_execution.Scanner", FakeScanner)
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.Downloader", FakeDownloader
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.DetectionService",
        FakeDetectionService,
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.ClassificationService",
        FakeClassificationService,
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.YOLODetector",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.CropWriter",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.get_embedder",
        lambda: object(),
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.IdentityClassifier",
        lambda session: object(),
    )


def test_full_pipeline_handler_reports_numeric_batch_progress(
    engine, tmp_path: Path, monkeypatch
):
    # Regression test for issue #103's UI acceptance criterion: the "run
    # pipeline" job must drive JobProgressReporter.set(current=, total=),
    # not just progress.message(...), so the Jobs page's progress bar
    # actually moves during a run instead of sitting frozen at its initial
    # state for the whole job.
    _patch_pipeline_dependencies(monkeypatch)

    config = Config(
        immich_url="http://fake",
        immich_api_key="key",
        state_dir=tmp_path,
        cache_dir=tmp_path,
        yolo_model=tmp_path / "unused.pt",
        crop_padding=0.0,
    )

    with Session(engine) as session:
        handler = _full_pipeline_handler(session, config, {})
        progress = RecordingProgress()
        result = handler(progress)

    total = BATCH_SIZE + 500

    assert result["downloaded"] == total
    assert result["detected"] == total
    assert result["classified"] == total

    # An initial 0/total baseline before any batch runs, current climbing
    # across batches, and the final (harmless, idempotent) empty-probe
    # batch that confirms nothing's left.
    assert progress.sets == [
        (0, total),
        (BATCH_SIZE, total),
        (total, total),
        (total, total),
    ]
