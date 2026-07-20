from immich_dog_tagger.services.review import ReviewItem
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
    )

    output = tmp_path / "review"

    count = ReviewExporter().export(
        [item],
        output,
    )

    assert count == 1
    assert (output / "manifest.csv").exists()
    assert (output / "predicted" / "Fibs" / "crop.jpg").exists()
