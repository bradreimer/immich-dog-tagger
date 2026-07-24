import csv
from immich_dog_tagger.services.review_query import ReviewItem
from immich_dog_tagger.review_export import ReviewExporter


def test_export_review(tmp_path):
    source = tmp_path / "crop.jpg"
    source.write_text("test")

    item = ReviewItem(
        classification_id=1,
        crop_id=2,
        identity="Fibs",
        confidence=0.95,
        path=source,
        matched_example_path=None,
    )

    output = tmp_path / "review"

    count = ReviewExporter().export(
        [item],
        output,
    )

    assert count == 1
    assert (output / "manifest.csv").exists()
    assert (output / "predicted" / "Fibs" / "crop.jpg").exists()

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
        identity="Fibs",
        confidence=0.95,
        path=source,
        matched_example_path=example,
    )

    output = tmp_path / "review"

    ReviewExporter().export(
        [item],
        output,
    )

    metadata = output / "predicted" / "Fibs" / "crop.txt"

    assert metadata.exists()

    contents = metadata.read_text()

    assert "Fibs" in contents
    assert "0.9500" in contents
    assert "example.jpg" in contents
