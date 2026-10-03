"""
Open-vocabulary detector for Photo Lookup's per-photo "Look harder" action
(issue #390, ADR-012).

Grounding DINO finds whatever a text prompt describes rather than a fixed
list of trained classes, so it tends to catch dogs YOLO misses (odd poses,
blur, costumes, partial occlusion). It's far slower than YOLO -- seconds to
a minute or more per photo on CPU -- which is why it only ever runs on one
photo a human asked about, never in the batch pipeline.

Runs fully in-process: weights download once from Hugging Face (or load from
a local directory), and no image data leaves the machine.
"""

import importlib.util
import logging
from threading import Lock

from .detector import DetectionResult, ObjectDetector
from .enums import DetectorKind, Species
from .images import open_upright

logger = logging.getLogger(__name__)

# One phrase per species, each ending in "." -- Grounding DINO's expected
# prompt format for several separate categories.
PROMPT = "a dog. a cat."

# Grounding DINO's own defaults for box/phrase confidence.
BOX_THRESHOLD = 0.3
TEXT_THRESHOLD = 0.25

# The same animal can match both phrases, giving two near-identical boxes
# with different labels. Class-agnostic suppression keeps the stronger one.
NMS_IOU_THRESHOLD = 0.5


def is_available() -> bool:
    """
    Whether Look harder can run at all. `transformers` is a regular
    dependency, so this is only False in an unusual install -- but checking
    keeps that case a clear "unavailable" instead of a failed job.
    """
    return importlib.util.find_spec("transformers") is not None


def species_for_label(text_label: str) -> Species | None:
    """
    Map a matched prompt phrase ("dog", "a dog", ...) back to the species
    the rest of the pipeline expects. None for anything else.
    """
    words = text_label.lower().split()

    if "dog" in words:
        return Species.DOG

    if "cat" in words:
        return Species.CAT

    return None


class GroundingDinoDetector(ObjectDetector):
    kind = DetectorKind.GROUNDING_DINO

    def __init__(
        self,
        model_id: str,
        device: str | None = None,
    ):
        self.model_id = model_id
        self.device = device
        self._processor = None
        self._model = None
        self._load_lock = Lock()

    def _load(self):
        # Deferred to first use: importing transformers and loading ~900 MB
        # of weights must never slow API startup or the batch pipeline.
        with self._load_lock:
            if self._model is None:
                import torch
                from transformers import (
                    AutoModelForZeroShotObjectDetection,
                    AutoProcessor,
                )

                if self.device is None:
                    self.device = "cuda" if torch.cuda.is_available() else "cpu"

                logger.info(
                    "Loading Look harder detector %s on %s",
                    self.model_id,
                    self.device,
                )

                self._processor = AutoProcessor.from_pretrained(self.model_id)
                self._model = (
                    AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id)
                    .to(self.device)
                    .eval()
                )

        return self._processor, self._model

    def detect(
        self,
        image_path: str,
        expected_size: tuple[int, int] | None = None,
    ) -> list[DetectionResult]:
        import torch
        from torchvision.ops import nms

        processor, model = self._load()

        # Same decode as YOLODetector, so boxes are in the coordinate space
        # CropWriter crops from (issue #137).
        image = open_upright(image_path, expected_size).convert("RGB")

        inputs = processor(images=image, text=PROMPT, return_tensors="pt").to(
            self.device
        )

        with torch.no_grad():
            outputs = model(**inputs)

        result = processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=BOX_THRESHOLD,
            text_threshold=TEXT_THRESHOLD,
            target_sizes=[(image.height, image.width)],
        )[0]

        boxes = result["boxes"].detach().cpu().float()
        scores = result["scores"].detach().cpu().float()
        text_labels = result["text_labels"]

        if len(boxes) == 0:
            return []

        detections: list[DetectionResult] = []

        for index in nms(boxes, scores, NMS_IOU_THRESHOLD).tolist():
            species = species_for_label(text_labels[index])

            if species is None:
                continue

            x1, y1, x2, y2 = boxes[index].tolist()

            detections.append(
                DetectionResult(
                    label=species.value,
                    confidence=float(scores[index].item()),
                    x1=max(0, int(x1)),
                    y1=max(0, int(y1)),
                    x2=min(image.width, int(x2)),
                    y2=min(image.height, int(y2)),
                )
            )

        return detections
