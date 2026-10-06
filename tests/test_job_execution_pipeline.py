from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.orm import Session

from immich_dog_tagger.config import Config, ImmichAccount
from immich_dog_tagger.services.accounts import AccountService
from immich_dog_tagger.services.job_execution import _full_pipeline_handler
from immich_dog_tagger.services.pipeline import BATCH_SIZE


class RecordingProgress:
    def __init__(self):
        self.messages: list[str] = []
        self.sets: list[tuple[int, int | None]] = []
        # Issue #346: _account_for_job() reads progress.job.account_id to
        # resolve which Immich account a job runs against. None means
        # "resolve to the default account" -- these tests don't exercise
        # multi-account behavior, so this fake job is never anything else.
        self.job = SimpleNamespace(account_id=None)

    def message(self, value):
        self.messages.append(value)

    def set(self, current=None, total=None, message=None):
        self.sets.append((current, total))

        if message is not None:
            self.messages.append(message)

    def is_cancel_requested(self):
        return False


class FakeScanner:
    def __init__(self, client, session, cache_dir=None, account_id=None):
        pass

    def scan(self, limit=None, force=False, should_cancel=None):
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

    def download_pending(self, limit=None, force=False, should_cancel=None):
        return self._take(limit)


class FakeDetectionService(PoolStage):
    def __init__(self, detector, session, cache_dir, crop_writer=None):
        super().__init__(BATCH_SIZE + 500)

    def run(self, limit=None, force=False, should_cancel=None):
        from immich_dog_tagger.services.detection import DetectionSummary

        n = self._take(limit)
        return DetectionSummary(processed=n, detections=n, dogs=n, cats=0)


class FakeClassificationService(PoolStage):
    def __init__(self, session, embedder, classifier, policy=None):
        super().__init__(BATCH_SIZE + 500)

    def classify(self, mode=None, limit=None, threshold=None, should_cancel=None):
        from immich_dog_tagger.services.classification import ClassificationSummary

        n = self._take(limit)
        return ClassificationSummary(classified=n, identities={})


def _patch_pipeline_dependencies(monkeypatch):
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution._create_client",
        lambda config, account: object(),
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
        # Takes the owner's policy too since #149; accept whatever the
        # production call passes rather than pinning the signature here.
        lambda *a, **k: object(),
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


def _two_account_config(tmp_path: Path) -> Config:
    return Config(
        immich_url="http://fake",
        immich_api_key="",
        state_dir=tmp_path,
        cache_dir=tmp_path,
        yolo_model=tmp_path / "unused.pt",
        crop_padding=0.0,
        accounts=(
            ImmichAccount(name="alice", api_key="key-a"),
            ImmichAccount(name="bob", api_key="key-b"),
        ),
    )


def _record_scanned_accounts(monkeypatch, fail_for: str | None = None) -> list[int]:
    _patch_pipeline_dependencies(monkeypatch)
    scanned_account_ids: list[int] = []

    class AccountRecordingScanner(FakeScanner):
        def __init__(self, client, session, cache_dir=None, account_id=None):
            self.account_id = account_id

        def scan(self, limit=None, force=False, should_cancel=None):
            if self.account_id == fail_for:
                raise RuntimeError("bad api key")

            scanned_account_ids.append(self.account_id)
            return 1

    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.Scanner", AccountRecordingScanner
    )
    # Nothing pending: each account's run is just its scan.
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.Downloader",
        lambda *a, **k: SimpleNamespace(download_pending=lambda **kw: 0),
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.DetectionService",
        lambda *a, **k: SimpleNamespace(
            run=lambda **kw: SimpleNamespace(dogs=0, cats=0)
        ),
    )
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.ClassificationService",
        lambda *a, **k: SimpleNamespace(
            classify=lambda **kw: SimpleNamespace(classified=0)
        ),
    )

    return scanned_account_ids


def test_full_pipeline_handler_runs_every_account_when_job_has_none(
    engine, tmp_path: Path, monkeypatch
):
    # A job with no account_id (API/schedule with no account selected) used
    # to resolve to the first account only, so photos in later accounts were
    # never scanned. It must cover every configured account.
    scanned_account_ids = _record_scanned_accounts(monkeypatch)
    config = _two_account_config(tmp_path)

    with Session(engine) as session:
        result = _full_pipeline_handler(session, config, {})(RecordingProgress())
        names = {
            account.id: account.name
            for account in AccountService(session).list_accounts()
        }

    assert sorted(names[i] for i in scanned_account_ids) == ["alice", "bob"]
    assert result["scanned"] == 2
    assert result["failed_accounts"] == 0


def test_full_pipeline_handler_explicit_account_runs_only_that_account(
    engine, tmp_path: Path, monkeypatch
):
    scanned_account_ids = _record_scanned_accounts(monkeypatch)
    config = _two_account_config(tmp_path)

    with Session(engine) as session:
        service = AccountService(session)
        service.sync_from_config(config)
        bob = service.get_by_name("bob")
        progress = RecordingProgress()
        progress.job = SimpleNamespace(account_id=bob.id)

        _full_pipeline_handler(session, config, {})(progress)

        assert scanned_account_ids == [bob.id]


def test_full_pipeline_handler_isolates_a_failing_account(
    engine, tmp_path: Path, monkeypatch
):
    config = _two_account_config(tmp_path)

    with Session(engine) as session:
        service = AccountService(session)
        service.sync_from_config(config)
        alice = service.get_by_name("alice")

        scanned_account_ids = _record_scanned_accounts(monkeypatch, fail_for=alice.id)
        progress = RecordingProgress()

        result = _full_pipeline_handler(session, config, {})(progress)

        assert scanned_account_ids == [service.get_by_name("bob").id]

    assert result["failed_accounts"] == 1
    assert any("alice" in message for message in progress.messages)


def test_full_pipeline_handler_fails_when_every_account_fails(
    engine, tmp_path: Path, monkeypatch
):
    import pytest

    _patch_pipeline_dependencies(monkeypatch)

    class BrokenScanner(FakeScanner):
        def scan(self, limit=None, force=False, should_cancel=None):
            raise RuntimeError("bad api key")

    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.Scanner", BrokenScanner
    )

    with Session(engine) as session, pytest.raises(RuntimeError, match="every account"):
        _full_pipeline_handler(session, _two_account_config(tmp_path), {})(
            RecordingProgress()
        )
