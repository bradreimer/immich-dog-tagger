from csv import DictWriter
from pathlib import Path
import shutil

from immich_dog_tagger.services.review import ReviewItem


class ReviewExporter:
    def export(
        self,
        items: list[ReviewItem],
        directory: Path,
    ) -> int:
        predicted = directory / "predicted"

        predicted.mkdir(
            parents=True,
            exist_ok=True,
        )

        confirmed = directory / "confirmed"

        for identity in ("Fibs", "Hermann", "Henri", "Unknown"):
            (predicted / identity).mkdir(
                parents=True,
                exist_ok=True,
            )

            (confirmed / identity).mkdir(
                parents=True,
                exist_ok=True,
            )

        with (directory / "manifest.csv").open(
            "w",
            newline="",
        ) as file:
            writer = DictWriter(
                file,
                fieldnames=[
                    "classification_id",
                    "crop_id",
                    "identity",
                    "confidence",
                    "filename",
                    "source_path",
                ],
            )

            writer.writeheader()

            for item in items:
                identity = item.identity or "Unknown"

                destination = predicted / identity / item.filename

                shutil.copy2(
                    item.path,
                    destination,
                )

                writer.writerow(
                    {
                        "classification_id": item.classification_id,
                        "crop_id": item.crop_id,
                        "identity": item.identity,
                        "confidence": item.confidence,
                        "filename": item.filename,
                        "source_path": str(item.path),
                    }
                )

        return len(items)
