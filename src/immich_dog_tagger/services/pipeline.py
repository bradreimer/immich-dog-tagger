from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class PipelineSummary:
    scanned: int
    downloaded: int
    detected: int
    classified: int


class PipelineService:
    def __init__(
        self,
        scanner,
        downloader,
        detector,
        classifier,
    ):
        self.scanner = scanner
        self.downloader = downloader
        self.detector = detector
        self.classifier = classifier

    def run(
        self,
        progress: Callable[[str], None] | None = None,
        limit: int | None = None,
    ) -> PipelineSummary:
        if progress:
            progress("Scanning Immich")

        scanned = self.scanner.scan()

        if progress:
            progress("Downloading assets")

        downloaded = self.downloader.download_pending(
            limit=limit,
        )

        if progress:
            progress("Detecting dogs")

        detected = self.detector.run(
            limit=limit,
        )

        if progress:
            progress("Classifying dogs")

        classified = self.classifier.classify_pending(
            limit=limit,
        )

        return PipelineSummary(
            scanned=scanned,
            downloaded=downloaded,
            detected=detected.dogs,
            classified=classified.classified,
        )
