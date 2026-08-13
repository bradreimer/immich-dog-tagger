import csv
from datetime import UTC, datetime

from immich_dog_tagger.review_export import ReviewExporter
from immich_dog_tagger.services.review_query import (
    ReviewItem,
    ReviewPrediction,
    ReviewSuggestion,
)


def test_export_review(tmp_path):
    source = tmp_path / "crop.jpg"
    source.write_text("test")

    item = ReviewItem(
        classification_id=1,
        crop_id=2,
        path=source,
        species="dog",
        prediction=ReviewPrediction(
            identity="Riley",
            similarity=0.95,
            candidates=[],
        ),
        suggestion=None,
    )

    output = tmp_path / "review"

    count = ReviewExporter().export(
        [item],
        output,
    )

    assert count == 1
    assert (output / "manifest.csv").exists()
    assert (output / "predicted" / "Riley" / "crop.jpg").exists()

    with (output / "manifest.csv").open() as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["source_path"] == str(source)
    assert rows[0]["filename"] == "crop.jpg"


def test_export_review_writes_metadata(tmp_path):
    source = tmp_path / "crop.jpg"
    source.write_text("test")

    example = tmp_path / "example.jpg"
    example.write_text("example")

    item = ReviewItem(
        classification_id=1,
        crop_id=2,
        path=source,
        species="dog",
        prediction=ReviewPrediction(
            identity="Riley",
            similarity=0.95,
            candidates=[],
        ),
        suggestion=ReviewSuggestion(
            identity="Riley",
            similarity=0.95,
            example_id=1,
            example_path=example,
            captured_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC),
        ),
        captured_at=datetime(2019, 3, 3, 9, 0, 0, tzinfo=UTC),
    )

    output = tmp_path / "review"

    ReviewExporter().export(
        [item],
        output,
    )

    metadata = output / "predicted" / "Riley" / "crop.txt"

    assert metadata.exists()

    contents = metadata.read_text()

    assert "Riley" in contents
    assert "0.9500" in contents
    assert "example.jpg" in contents
    assert "Photo captured at: 2019-03-03T09:00:00+00:00" in contents
    assert "Matched example captured at: 2024-06-01T12:00:00+00:00" in contents


def test_export_review_writes_metadata_with_unknown_captured_at(tmp_path):
    source = tmp_path / "crop.jpg"
    source.write_text("test")

    item = ReviewItem(
        classification_id=1,
        crop_id=2,
        path=source,
        species="dog",
        prediction=ReviewPrediction(
            identity="Riley",
            similarity=0.95,
            candidates=[],
        ),
        suggestion=None,
        captured_at=None,
    )

    output = tmp_path / "review"

    ReviewExporter().export(
        [item],
        output,
    )

    metadata = output / "predicted" / "Riley" / "crop.txt"

    assert "Photo captured at: Unknown" in metadata.read_text()
