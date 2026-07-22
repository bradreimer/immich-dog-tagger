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

    def run(self) -> PipelineSummary:
        scanned = self.scanner.scan()

        downloaded = self.downloader.download_pending()

        detected = self.detector.run()

        classified = self.classifier.classify_pending()

        return PipelineSummary(
            scanned=scanned,
            downloaded=downloaded,
            detected=detected.dogs,
            classified=classified.classified,
        )
