from pathlib import Path

from ultralytics import YOLO

from .detector import (
    DetectionResult,
    ObjectDetector,
)
from .images import open_upright


class YOLODetector(ObjectDetector):
    def __init__(
        self,
        model_path: Path,
        device: str | None = None,
    ):
        self.model = YOLO(str(model_path))

        self.device = device

    def detect(
        self,
        image_path: str,
    ) -> list[DetectionResult]:

        # Decoded here rather than handed to ultralytics as a path, so the
        # boxes below are expressed in the same coordinate space CropWriter
        # crops from. Ultralytics decodes a path with OpenCV, which applies
        # EXIF orientation, except for HEIC, where it falls back to Pillow,
        # which doesn't -- so which space its boxes came back in depended on
        # the file's format (issue #137). open_upright() is one defined
        # answer for every format.
        image = open_upright(image_path).convert("RGB")

        results = self.model.predict(
            source=image,
            device=self.device,
            verbose=False,
        )

        detections: list[DetectionResult] = []

        for result in results:
            for box in result.boxes:
                label = result.names[int(box.cls.item())]

                confidence = float(box.conf.item())

                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())

                detections.append(
                    DetectionResult(
                        label=label,
                        confidence=confidence,
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )
                )

        return detections
