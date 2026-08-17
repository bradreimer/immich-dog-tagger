import logging
from dataclasses import dataclass

from immich_dog_tagger.enums import ClassificationMode
from immich_dog_tagger.services.pipeline import BATCH_SIZE, PipelineService


@dataclass
class FakeDetectionSummary:
    dogs: int
    cats: int = 0


@dataclass
class FakeClassificationSummary:
    classified: int


class FakeScanner:
    def __init__(self, scanned=10):
        self.called = False
        self.limit = None
        self.force = None
        self._scanned = scanned

    def scan(
        self,
        limit=None,
        force=False,
    ):
        self.called = True
        self.limit = limit
        self.force = force
        return self._scanned


class FakeDownloader:
    """Returns `count` on its first call and 0 after, like the real
    status-filtered query once everything it found has been downloaded."""

    def __init__(self, count=8):
        self.called = False
        self.calls = 0
        self._count = count

    def download_pending(
        self,
        limit=None,
        force=False,
    ):
        self.called = True
        self.calls += 1
        return self._count if self.calls == 1 else 0


class FakeDetector:
    def __init__(self, dogs=5):
        self.called = False
        self.calls = 0
        self._dogs = dogs

    def run(
        self,
        limit=None,
        force=False,
    ):
        self.called = True
        self.calls += 1
        return FakeDetectionSummary(
            dogs=self._dogs if self.calls == 1 else 0,
        )


class FakeClassifier:
    def __init__(self, classified=5):
        self.called = False
        self.calls = 0
        self._classified = classified

    def classify(
        self,
        limit=None,
        mode=None,
    ):
        self.called = True
        self.calls += 1
        return FakeClassificationSummary(
            classified=self._classified if self.calls == 1 else 0,
        )


class PoolDownloader:
    """Simulates a status-filtered query draining a fixed-size backlog:
    each call returns min(limit, remaining) and advances."""

    def __init__(self, total):
        self.remaining = total
        self.limits = []

    def download_pending(self, limit=None, force=False):
        self.limits.append(limit)
        n = min(limit, self.remaining) if limit is not None else self.remaining
        self.remaining -= n
        return n


class PoolDetector:
    def __init__(self, total):
        self.remaining = total
        self.limits = []

    def run(self, limit=None, force=False):
        self.limits.append(limit)
        n = min(limit, self.remaining) if limit is not None else self.remaining
        self.remaining -= n
        return FakeDetectionSummary(dogs=n)


class PoolClassifier:
    def __init__(self, total):
        self.remaining = total
        self.limits = []

    def classify(self, limit=None, mode=None):
        self.limits.append(limit)
        n = min(limit, self.remaining) if limit is not None else self.remaining
        self.remaining -= n
        return FakeClassificationSummary(classified=n)


def test_pipeline_runs_all_steps():
    scanner = FakeScanner()
    downloader = FakeDownloader()
    detector = FakeDetector()
    classifier = FakeClassifier()

    service = PipelineService(
        scanner,
        downloader,
        detector,
        classifier,
    )

    summary = service.run()

    assert summary.scanned == 10
    assert summary.downloaded == 8
    assert summary.detected == 5
    assert summary.classified == 5

    assert scanner.called
    assert downloader.called
    assert detector.called
    assert classifier.called


def test_pipeline_runs_steps_in_order():
    calls = []

    class OrderedScanner:
        def scan(self, limit=None, force=False):
            calls.append("scan")
            return 1

    class OrderedDownloader:
        def __init__(self):
            self.n = 0

        def download_pending(self, limit=None, force=False):
            calls.append("download")
            self.n += 1
            return 1 if self.n == 1 else 0

    class OrderedDetector:
        def __init__(self):
            self.n = 0

        def run(self, limit=None, force=False):
            calls.append("detect")
            self.n += 1

            return FakeDetectionSummary(
                dogs=1 if self.n == 1 else 0,
            )

    class OrderedClassifier:
        def __init__(self):
            self.n = 0

        def classify(self, limit=None, mode=None):
            calls.append("classify")
            self.n += 1

            return FakeClassificationSummary(
                classified=1 if self.n == 1 else 0,
            )

    service = PipelineService(
        OrderedScanner(),
        OrderedDownloader(),
        OrderedDetector(),
        OrderedClassifier(),
    )

    service.run()

    # One batch finds work, a second (empty) batch confirms the backlog is
    # drained before the loop stops.
    assert calls == [
        "scan",
        "download",
        "detect",
        "classify",
        "download",
        "detect",
        "classify",
    ]


def test_pipeline_reports_progress():
    messages = []

    service = PipelineService(
        FakeScanner(),
        FakeDownloader(),
        FakeDetector(),
        FakeClassifier(),
    )

    service.run(
        progress=messages.append,
    )

    assert messages == [
        "Scanning Immich",
        "Scanned 10 assets",
        "Downloading assets",
        "Downloaded 8 assets",
        "Detecting dogs and cats",
        "Detected 5 dog(s) and 0 cat(s)",
        "Classifying crops",
        "Classified 5 crops",
        "Full pipeline batch 1 complete: 8/10 asset(s) processed this run",
        "Downloading assets",
        "Downloaded 0 assets",
        "Detecting dogs and cats",
        "Detected 0 dog(s) and 0 cat(s)",
        "Classifying crops",
        "Classified 0 crops",
    ]


def test_pipeline_passes_limit_to_steps():
    received = {}

    class LimitedDownloader:
        def download_pending(self, limit=None, force=False):
            received["download"] = limit
            return 0

    class LimitedDetector:
        def run(self, limit=None, force=False):
            received["detect"] = limit
            return FakeDetectionSummary(dogs=0)

    class LimitedClassifier:
        def classify(self, limit=None, mode=None):
            received["classify"] = limit
            return FakeClassificationSummary(classified=0)

    scanner = FakeScanner()

    service = PipelineService(
        scanner,
        LimitedDownloader(),
        LimitedDetector(),
        LimitedClassifier(),
    )

    service.run(limit=25)

    assert scanner.limit == 25

    assert received == {
        "download": 25,
        "detect": 25,
        "classify": 25,
    }


def test_pipeline_passes_force_to_steps():
    received = {}

    class ForcedScanner:
        def scan(self, limit=None, force=False):
            received["scan"] = force
            return 0

    class ForcedDownloader:
        def download_pending(self, limit=None, force=False):
            received["download"] = force
            return 0

    class ForcedDetector:
        def run(self, limit=None, force=False):
            received["detect"] = force
            return FakeDetectionSummary(dogs=0)

    class ForcedClassifier:
        def classify(self, limit=None, mode=None):
            received["classify"] = mode == ClassificationMode.ALL
            return FakeClassificationSummary(classified=0)

    service = PipelineService(
        ForcedScanner(),
        ForcedDownloader(),
        ForcedDetector(),
        ForcedClassifier(),
    )

    service.run(force=True)

    assert received == {
        "scan": True,
        "download": True,
        "detect": True,
        "classify": True,
    }


def test_pipeline_force_mode_does_not_batch():
    """force=True reprocesses rows via an unfiltered query with no notion
    of "what's left", so it must run each stage exactly once regardless of
    how much work is reported -- looping would just replay the same rows."""

    downloader = FakeDownloader(count=5000)
    detector = FakeDetector(dogs=5000)
    classifier = FakeClassifier(classified=5000)

    service = PipelineService(
        FakeScanner(),
        downloader,
        detector,
        classifier,
    )

    summary = service.run(force=True)

    assert downloader.calls == 1
    assert detector.calls == 1
    assert classifier.calls == 1

    assert summary.downloaded == 5000
    assert summary.detected == 5000
    assert summary.classified == 5000


def test_pipeline_batches_large_backlog_in_chunks(caplog):
    total = 2 * BATCH_SIZE + 500

    scanner = FakeScanner(scanned=total)
    downloader = PoolDownloader(total)
    detector = PoolDetector(total)
    classifier = PoolClassifier(total)

    service = PipelineService(
        scanner,
        downloader,
        detector,
        classifier,
    )

    with caplog.at_level(logging.INFO, logger="immich_dog_tagger.services.pipeline"):
        summary = service.run()

    assert summary.downloaded == total
    assert summary.detected == total
    assert summary.classified == total

    # Requests BATCH_SIZE each call; the final call finds nothing left and
    # stops the loop without starting another batch.
    assert downloader.limits == [BATCH_SIZE, BATCH_SIZE, BATCH_SIZE, BATCH_SIZE]

    batch_logs = [r.message for r in caplog.records if "batch" in r.message.lower()]

    assert batch_logs == [
        f"Full pipeline batch 1 complete: {BATCH_SIZE}/{total} asset(s) processed this run",
        f"Full pipeline batch 2 complete: {2 * BATCH_SIZE}/{total} asset(s) processed this run",
        f"Full pipeline batch 3 complete: {total}/{total} asset(s) processed this run",
    ]


def test_pipeline_respects_explicit_limit_across_multiple_batches():
    limit = 2 * BATCH_SIZE + 500

    scanner = FakeScanner(scanned=10_000)
    downloader = PoolDownloader(10_000)
    detector = PoolDetector(10_000)
    classifier = PoolClassifier(10_000)

    service = PipelineService(
        scanner,
        downloader,
        detector,
        classifier,
    )

    summary = service.run(limit=limit)

    assert summary.downloaded == limit
    assert summary.detected == limit
    assert summary.classified == limit

    # Stops once `limit` has been requested, even though far more (10,000)
    # was available -- no extra probe batch beyond what `limit` allows.
    assert downloader.limits == [BATCH_SIZE, BATCH_SIZE, 500]


def test_pipeline_small_library_processes_in_a_single_batch(caplog):
    total = 300

    scanner = FakeScanner(scanned=total)
    downloader = PoolDownloader(total)
    detector = PoolDetector(total)
    classifier = PoolClassifier(total)

    service = PipelineService(
        scanner,
        downloader,
        detector,
        classifier,
    )

    with caplog.at_level(logging.INFO, logger="immich_dog_tagger.services.pipeline"):
        summary = service.run()

    assert summary.downloaded == total
    assert summary.detected == total
    assert summary.classified == total

    batch_logs = [r.message for r in caplog.records if "batch" in r.message.lower()]

    assert batch_logs == [
        f"Full pipeline batch 1 complete: {total}/{total} asset(s) processed this run",
    ]
