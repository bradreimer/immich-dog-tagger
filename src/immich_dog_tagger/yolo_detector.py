from pathlib import Path

from ultralytics import YOLO

from .detector import (
    DetectionResult,
    ObjectDetector,
)


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

        results = self.model.predict(
            source=image_path,
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
