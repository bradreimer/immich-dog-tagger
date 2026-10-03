from dataclasses import dataclass

from .enums import DetectorKind


@dataclass(frozen=True)
class DetectionResult:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


class ObjectDetector:
    # Recorded on each Detection this detector produces (issue #390).
    # Defaults to YOLO, the pipeline's detector, so a test double standing in
    # for it needs no extra setup.
    kind: DetectorKind = DetectorKind.YOLO

    def detect(
        self,
        image_path: str,
        expected_size: tuple[int, int] | None = None,
    ) -> list[DetectionResult]:
        raise NotImplementedError
