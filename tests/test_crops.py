import logging
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


def test_crop_writer_handles_rgba_source_image(tmp_path: Path):
    image_path = tmp_path / "test.png"

    # PNGs (and other formats) can carry an alpha channel; JPEG can't
    # encode one, so the writer must normalize mode before saving.
    image = Image.new(
        "RGBA",
        (100, 100),
        (255, 255, 255, 128),
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
    ]

    crops = writer.write(
        image_path,
        "rgba",
        detections,
    )

    assert len(crops) == 1

    crop_path = crop_dir / "rgba_0.jpg"

    assert crop_path.exists()

    cropped = Image.open(crop_path)

    assert cropped.mode == "RGB"


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


def test_crop_writer_skips_detection_entirely_outside_image_bounds(
    tmp_path: Path,
    caplog,
):
    # Regression test for issue #88: a detection box whose raw coordinates
    # fall entirely outside the image (e.g. from a detector/decoder
    # dimension mismatch) used to reach Image.crop() with an inverted box
    # -- "Coordinate 'lower' is less than 'upper'" -- crashing the whole
    # pipeline job instead of being skipped.
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
            confidence=0.9,
            x1=150,
            y1=150,
            x2=180,
            y2=180,
        ),
    ]

    with caplog.at_level("WARNING"):
        crops = writer.write(
            image_path,
            "out-of-bounds",
            detections,
        )

    assert crops == []
    assert not any(crop_dir.iterdir())
    assert "outside image bounds" in caplog.text


def test_crop_writer_clamps_partially_out_of_bounds_detection(tmp_path: Path):
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

    # y2 extends beyond the image height; the crop should still be
    # produced, clamped to the actual image bounds.
    detections = [
        DetectionResult(
            label="dog",
            confidence=0.9,
            x1=50,
            y1=50,
            x2=90,
            y2=150,
        ),
    ]

    crops = writer.write(
        image_path,
        "partial",
        detections,
    )

    assert len(crops) == 1

    crop_path = crop_dir / "partial_0.jpg"
    crop = Image.open(crop_path)

    # Clamped box before padding: (50,50)-(90,100). 15% padding on the
    # clamped 40x50 box adds 6px/7px, then re-clamps to the image bounds:
    # (44,43)-(96,100) -> 52x57.
    assert crop.size == (
        52,
        57,
    )


def _write_rotated_source(
    path: Path,
    orientation: int = 6,
) -> Image.Image:
    """
    Write a JPEG that is stored landscape but tagged to display portrait.

    Returns the upright image the tag describes -- the frame the detector
    sees, and therefore the frame its boxes are expressed in.
    """
    # Upright: 100x200 portrait, with a red marker in a known place.
    upright = Image.new("RGB", (100, 200), "white")
    upright.paste(Image.new("RGB", (40, 40), "red"), (10, 10))

    # Stored: the pixels a camera would actually write for orientation 6,
    # i.e. the upright frame turned so the tag turns it back.
    stored = upright.transpose(Image.Transpose.ROTATE_90)

    exif = stored.getexif()
    exif[274] = orientation

    stored.save(path, exif=exif)

    return upright


def test_crop_writer_honours_exif_orientation(tmp_path: Path):
    """
    Regression test for issue #137.

    The detector decodes with EXIF orientation applied, so its boxes are in
    the upright frame. Before the fix CropWriter decoded the same file
    without applying it, and cut the box out of the raw landscape buffer --
    a different region of the photo, rotated.
    """
    image_path = tmp_path / "portrait.jpg"

    upright = _write_rotated_source(image_path)

    # Sanity check that the fixture really is orientation-dependent: stored
    # landscape, displayed portrait.
    assert Image.open(image_path).size == (200, 100)
    assert upright.size == (100, 200)

    writer = CropWriter(
        tmp_path / "crops",
        padding=0.0,
    )

    # The red marker's coordinates in the upright frame.
    detections = [
        DetectionResult(
            label="dog",
            confidence=0.95,
            x1=10,
            y1=10,
            x2=50,
            y2=50,
        ),
    ]

    crops = writer.write(
        image_path,
        "rotated",
        detections,
    )

    assert len(crops) == 1

    cropped = Image.open(crops[0][1]).convert("RGB")

    assert cropped.size == (40, 40)

    # Every pixel of the crop should be the marker. Sampled with a tolerance
    # because the crop is written as JPEG.
    for point in ((2, 2), (20, 20), (37, 37)):
        red, green, blue = cropped.getpixel(point)

        assert red > 200 and green < 80 and blue < 80, (
            f"crop pixel {point} is {(red, green, blue)}, not the marker -- "
            "the box was applied to the wrong coordinate space"
        )


def test_crop_writer_uses_upright_bounds_for_the_out_of_bounds_check(
    tmp_path: Path,
    caplog,
):
    """
    A box that is valid in the upright frame but would overflow the stored
    landscape frame must not be treated as out of bounds (issue #137 is the
    root cause of the out-of-bounds boxes in issue #88).
    """
    image_path = tmp_path / "portrait.jpg"

    _write_rotated_source(image_path)

    writer = CropWriter(
        tmp_path / "crops",
        padding=0.0,
    )

    # y2=190 fits the upright 100x200 frame, but not the stored 200x100 one.
    detections = [
        DetectionResult(
            label="dog",
            confidence=0.9,
            x1=10,
            y1=150,
            x2=50,
            y2=190,
        ),
    ]

    with caplog.at_level(logging.WARNING):
        crops = writer.write(
            image_path,
            "rotated",
            detections,
        )

    assert len(crops) == 1
    assert Image.open(crops[0][1]).size == (40, 40)
    assert "outside image bounds" not in caplog.text


def test_crop_writer_is_unchanged_for_untagged_images(tmp_path: Path):
    image_path = tmp_path / "untagged.jpg"

    image = Image.new("RGB", (100, 200), "white")
    image.paste(Image.new("RGB", (40, 40), "red"), (10, 10))
    image.save(image_path)

    writer = CropWriter(
        tmp_path / "crops",
        padding=0.0,
    )

    crops = writer.write(
        image_path,
        "untagged",
        [
            DetectionResult(
                label="dog",
                confidence=0.9,
                x1=10,
                y1=10,
                x2=50,
                y2=50,
            )
        ],
    )

    cropped = Image.open(crops[0][1]).convert("RGB")

    assert cropped.size == (40, 40)

    red, green, blue = cropped.getpixel((20, 20))

    assert red > 200 and green < 80 and blue < 80
