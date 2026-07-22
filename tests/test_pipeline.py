from dataclasses import dataclass

from immich_dog_tagger.services.pipeline import PipelineService


@dataclass
class FakeDetectionSummary:
    dogs: int


@dataclass
class FakeClassificationSummary:
    classified: int


class FakeScanner:
    def __init__(self):
        self.called = False

    def scan(self):
        self.called = True
        return 10


class FakeDownloader:
    def __init__(self):
        self.called = False

    def download_pending(
        self,
        limit=None,
    ):
        self.called = True
        return 8


class FakeDetector:
    def __init__(self):
        self.called = False

    def run(
        self,
        limit=None,
    ):
        self.called = True
        return FakeDetectionSummary(
            dogs=5,
        )


class FakeClassifier:
    def __init__(self):
        self.called = False

    def classify_pending(
        self,
        limit=None,
    ):
        self.called = True
        return FakeClassificationSummary(
            classified=5,
        )


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
        def scan(self):
            calls.append("scan")
            return 1

    class OrderedDownloader:
        def download_pending(
            self,
            limit=None,
        ):
            calls.append("download")
            return 1

    class OrderedDetector:
        def run(
            self,
            limit=None,
        ):
            calls.append("detect")

            return FakeDetectionSummary(
                dogs=1,
            )

    class OrderedClassifier:
        def classify_pending(
            self,
            limit=None,
        ):
            calls.append("classify")

            return FakeClassificationSummary(
                classified=1,
            )

    service = PipelineService(
        OrderedScanner(),
        OrderedDownloader(),
        OrderedDetector(),
        OrderedClassifier(),
    )

    service.run()

    assert calls == [
        "scan",
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
        "Downloading assets",
        "Detecting dogs",
        "Classifying dogs",
    ]


def test_pipeline_passes_limit_to_steps():
    received = {}

    class LimitedDownloader:
        def download_pending(self, limit=None):
            received["download"] = limit
            return 0

    class LimitedDetector:
        def run(self, limit=None):
            received["detect"] = limit
            return FakeDetectionSummary(dogs=0)

    class LimitedClassifier:
        def classify_pending(self, limit=None):
            received["classify"] = limit
            return FakeClassificationSummary(classified=0)

    service = PipelineService(
        FakeScanner(),
        LimitedDownloader(),
        LimitedDetector(),
        LimitedClassifier(),
    )

    service.run(limit=25)

    assert received == {
        "download": 25,
        "detect": 25,
        "classify": 25,
    }
