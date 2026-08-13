import shutil
from csv import DictWriter
from pathlib import Path

from immich_dog_tagger.services.review_query import ReviewItem


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
                identity = item.prediction.identity or "Unknown"

                destination = predicted / identity / item.filename

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                (confirmed / identity).mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    item.path,
                    destination,
                )

                self._write_metadata(
                    destination,
                    item,
                )

                writer.writerow(
                    {
                        "classification_id": item.classification_id,
                        "crop_id": item.crop_id,
                        "identity": item.prediction.identity or "Unknown",
                        "confidence": item.prediction.similarity,
                        "filename": item.filename,
                        "source_path": str(item.path),
                    }
                )

        return len(items)

    def _write_metadata(
        self,
        destination: Path,
        item: ReviewItem,
    ) -> None:
        metadata = destination.with_suffix(".txt")

        lines = [
            f"Identity: {item.prediction.identity or 'Unknown'}",
            f"Similarity: {item.prediction.similarity:.4f}",
        ]

        if item.captured_at:
            lines.append(f"Photo captured at: {item.captured_at.isoformat()}")
        else:
            lines.append("Photo captured at: Unknown")

        if item.suggestion and item.suggestion.example_path:
            lines.append(f"Matched example: {item.suggestion.example_path}")
        else:
            lines.append("Matched example: None")

        if item.suggestion and item.suggestion.captured_at:
            lines.append(
                f"Matched example captured at: {item.suggestion.captured_at.isoformat()}"
            )

        metadata.write_text(
            "\n".join(lines),
        )
