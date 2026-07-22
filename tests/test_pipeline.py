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

    def download_pending(self):
        self.called = True
        return 8


class FakeDetector:
    def __init__(self):
        self.called = False

    def run(self):
        self.called = True
        return FakeDetectionSummary(
            dogs=5,
        )


class FakeClassifier:
    def __init__(self):
        self.called = False

    def classify_pending(self):
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
        def download_pending(self):
            calls.append("download")
            return 1

    class OrderedDetector:
        def run(self):
            calls.append("detect")

            return FakeDetectionSummary(
                dogs=1,
            )

    class OrderedClassifier:
        def classify_pending(self):
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
