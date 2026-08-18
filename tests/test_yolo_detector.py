from pathlib import Path

import pytest
from PIL import Image

from immich_dog_tagger import yolo_detector
from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.detector import DetectionResult
from immich_dog_tagger.yolo_detector import YOLODetector


class FakeYOLO:
    """
    Stands in for ultralytics' YOLO so the detector's image handling can be
    tested without model weights or an inference run.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.sources: list = []

    def predict(self, source, device=None, verbose=False):
        self.sources.append(source)

        return []


@pytest.fixture
def fake_yolo(monkeypatch):
    created: list[FakeYOLO] = []

    def factory(model_path: str) -> FakeYOLO:
        model = FakeYOLO(model_path)
        created.append(model)

        return model

    monkeypatch.setattr(yolo_detector, "YOLO", factory)

    return created


def _write_rotated_source(path: Path) -> None:
    # Stored landscape (200x100), tagged to display portrait (100x200).
    stored = Image.new("RGB", (100, 200), "white").transpose(Image.Transpose.ROTATE_90)

    exif = stored.getexif()
    exif[274] = 6

    stored.save(path, exif=exif)


def test_detector_and_crop_writer_agree_on_the_image_frame(
    tmp_path: Path,
    fake_yolo,
    monkeypatch,
):
    """
    The whole point of issue #137: if these two disagree about the source
    image's dimensions, every box the detector produces is interpreted in
    the wrong coordinate space by the cropper.
    """
    image_path = tmp_path / "portrait.jpg"

    _write_rotated_source(image_path)

    detector = YOLODetector(tmp_path / "model.pt")

    detector.detect(str(image_path))

    (source,) = fake_yolo[0].sources

    assert isinstance(source, Image.Image)

    # Ultralytics converts a PIL image's channels itself, so it must be RGB.
    assert source.mode == "RGB"

    detector_size = source.size

    # Capture the frame CropWriter actually crops from.
    cropped_from: list[tuple[int, int]] = []

    original_crop = Image.Image.crop

    def recording_crop(self, box):
        cropped_from.append(self.size)

        return original_crop(self, box)

    monkeypatch.setattr(Image.Image, "crop", recording_crop)

    CropWriter(tmp_path / "crops").write(
        image_path,
        "portrait",
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

    assert cropped_from == [detector_size]
    assert detector_size == (100, 200)
