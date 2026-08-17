import logging
from collections.abc import Callable
from dataclasses import dataclass

from immich_dog_tagger.enums import ClassificationMode

logger = logging.getLogger(__name__)

# Download/detect/classify run in chunks of this size rather than one pass
# across the whole library, so a large first-time run starts producing
# reviewable crops after the first batch instead of only once every asset
# has been processed (issue #103). Matches scanner.BATCH_SIZE /
# downloader.BATCH_SIZE (issue #99/#100), which batch DB commits for a
# related reason; kept as its own constant since this module deliberately
# stays decoupled from those concrete classes (its dependencies are
# duck-typed, see __init__ below).
BATCH_SIZE = 1000


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
        on_batch_progress: Callable[[int, int], None] | None = None,
        limit: int | None = None,
        force: bool = False,
        should_cancel: Callable[[], bool] | None = None,
    ) -> PipelineSummary:
        def report(message: str) -> None:
            if progress:
                progress(message)

        def report_progress(current: int, total: int) -> None:
            if on_batch_progress:
                on_batch_progress(current, total)

        # Scan Immich for new assets
        report("Scanning Immich")

        scanned = self.scanner.scan(
            limit=limit,
            force=force,
            should_cancel=should_cancel,
        )

        report(f"Scanned {scanned} assets")
        report_progress(0, scanned)

        mode = ClassificationMode.ALL if force else ClassificationMode.PENDING

        # `force` reprocesses rows via an unfiltered query (see
        # Downloader.download_pending), so repeated calls have no notion of
        # "what's left" to advance through -- batching it would just replay
        # the same first BATCH_SIZE rows forever. Only the default
        # (non-force) path, whose per-stage queries filter by status, can
        # safely be looped in batches.
        batched = not force

        total_downloaded = 0
        total_dogs = 0
        total_cats = 0
        total_classified = 0

        remaining = limit
        batch_number = 0
        progress_total = scanned

        while True:
            if should_cancel and should_cancel():
                break

            batch_limit = BATCH_SIZE if batched else limit

            if batched and remaining is not None:
                batch_limit = min(batch_limit, remaining)

                if batch_limit <= 0:
                    break

            report("Downloading assets")

            downloaded = self.downloader.download_pending(
                limit=batch_limit,
                force=force,
                should_cancel=should_cancel,
            )

            report(f"Downloaded {downloaded} assets")

            report("Detecting dogs and cats")

            detected = self.detector.run(
                limit=batch_limit,
                force=force,
                should_cancel=should_cancel,
            )

            report(f"Detected {detected.dogs} dog(s) and {detected.cats} cat(s)")

            report("Classifying crops")

            classified = self.classifier.classify(
                limit=batch_limit,
                mode=mode,
                should_cancel=should_cancel,
            )

            report(f"Classified {classified.classified} crops")

            total_downloaded += downloaded
            total_dogs += detected.dogs
            total_cats += detected.cats
            total_classified += classified.classified

            made_progress = (
                downloaded > 0
                or detected.dogs > 0
                or detected.cats > 0
                or classified.classified > 0
            )

            # Grown unconditionally (not just on a batch that made progress)
            # so force mode's single unbatched pass -- which can process far
            # more than `scanned` reported, since its query has no status
            # filter to size against -- still ends with a sensible total
            # rather than one stuck at the scan count.
            progress_total = max(progress_total, total_downloaded)

            if batched and made_progress:
                batch_number += 1

                batch_message = (
                    f"Full pipeline batch {batch_number} complete: "
                    f"{total_downloaded}/{progress_total} asset(s) processed this run"
                )

                report(batch_message)
                logger.info(batch_message)

            report_progress(total_downloaded, progress_total)

            if remaining is not None:
                remaining -= batch_limit

            if not batched or not made_progress:
                break

        return PipelineSummary(
            scanned=scanned,
            downloaded=total_downloaded,
            detected=total_dogs + total_cats,
            classified=total_classified,
        )
