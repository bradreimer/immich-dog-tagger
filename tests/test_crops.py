from pathlib import Path

from PIL import Image

from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.detector import DetectionResult


def test_crop_writer_creates_padded_dog_crop(tmp_path: Path):
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

    crops = writer.write(
        image_path,
        "abc123",
        detections,
    )

    assert len(crops) == 1

    crop_path = crop_dir / "abc123_0.jpg"

    assert crop_path.exists()
    assert crops[0] == (0, crop_path)

    cropped = Image.open(crop_path)

    # Expecting 50x60 + 15% padding on each side, resulting in 64x78
    assert cropped.size == (
        64,
        78,
    )


def test_crop_writer_keeps_cat_detections_too(tmp_path: Path):
    image_path = tmp_path / "test.jpg"

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
            label="cat",
            confidence=0.92,
            x1=5,
            y1=5,
            x2=40,
            y2=40,
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

    crops = writer.write(
        image_path,
        "mixed",
        detections,
    )

    # Union of dog + cat detections; "person" (or any other COCO class)
    # still excluded -- species is hardcoded to exactly these two.
    assert len(crops) == 2
    assert crops[0][0] == 0
    assert crops[1][0] == 1
    assert (crop_dir / "mixed_0.jpg").exists()
    assert (crop_dir / "mixed_1.jpg").exists()
    assert not (crop_dir / "mixed_2.jpg").exists()


def test_crop_writer_clips_crop_to_image_bounds(tmp_path: Path):
    image_path = tmp_path / "test.jpg"

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
            x1=0,
            y1=0,
            x2=20,
            y2=20,
        ),
    ]

    crops = writer.write(
        image_path,
        "edge",
        detections,
    )

    assert len(crops) == 1

    crop_path = crop_dir / "edge_0.jpg"
    crop = Image.open(crop_path)

    # Original 20x20 box receives 15% padding (3px each side),
    # but negative coordinates are clipped to the image boundary:
    # (-3,-3)-(23,23) becomes (0,0)-(23,23).
    assert crop.size == (
        23,
        23,
    )
