from collections.abc import Callable
from dataclasses import dataclass

from immich_dog_tagger.enums import ClassificationMode


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
        force: bool = False,
    ) -> PipelineSummary:
        # Scan Immich for new assets
        if progress:
            progress("Scanning Immich")

        scanned = self.scanner.scan(
            limit=limit,
            force=force,
        )

        if progress:
            progress(f"Scanned {scanned} assets")

        # Download pending assets
        if progress:
            progress("Downloading assets")

        downloaded = self.downloader.download_pending(
            limit=limit,
            force=force,
        )

        if progress:
            progress(f"Downloaded {downloaded} assets")

        # Detect dogs and cats in downloaded assets
        if progress:
            progress("Detecting dogs and cats")

        detected = self.detector.run(
            limit=limit,
            force=force,
        )

        if progress:
            progress(f"Detected {detected.dogs} dog(s) and {detected.cats} cat(s)")

        # Classify detected crops
        if progress:
            progress("Classifying crops")

        mode = ClassificationMode.ALL if force else ClassificationMode.PENDING

        classified = self.classifier.classify(
            limit=limit,
            mode=mode,
        )

        if progress:
            progress(f"Classified {classified.classified} crops")

        return PipelineSummary(
            scanned=scanned,
            downloaded=downloaded,
            detected=detected.dogs + detected.cats,
            classified=classified.classified,
        )
