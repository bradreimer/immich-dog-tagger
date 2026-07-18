from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionResult:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


class ObjectDetector:
    def detect(
        self,
        image_path: str,
    ) -> list[DetectionResult]:
        raise NotImplementedError