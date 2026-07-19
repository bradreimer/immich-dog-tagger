from pathlib import Path

from PIL import Image

from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.detector import DetectionResult


def test_crop_writer_creates_dog_crop(tmp_path: Path):
    image_path = tmp_path / "test.jpg"

    # Create a simple 100x100 test image
    image = Image.new(
        "RGB",
        (100, 100),
        "white",
    )

    image.save(image_path)

    crop_dir = tmp_path / "crops"

    writer = CropWriter(
        crop_dir,
    )

    detections = [
        DetectionResult(
            label="dog",
            confidence=0.95,
            x1=10,
            y1=20,
            x2=60,
            y2=80,
        ),
        DetectionResult(
            label="person",
            confidence=0.90,
            x1=0,
            y1=0,
            x2=50,
            y2=50,
        ),
    ]

    count = writer.write(
        image_path,
        "abc123",
        detections,
    )

    assert count == 1

    crop_path = (
        crop_dir
        / "abc123_0.jpg"
    )

    assert crop_path.exists()

    cropped = Image.open(crop_path)

    assert cropped.size == (
        50,
        60,
    )