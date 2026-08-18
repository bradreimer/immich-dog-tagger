import logging
from pathlib import Path

from .enums import Species
from .images import open_upright

logger = logging.getLogger(__name__)

_DETECTABLE_LABELS = {species.value for species in Species}


class CropWriter:
    def __init__(
        self,
        crop_dir: Path,
        padding: float = 0.15,
    ):
        self.crop_dir = crop_dir
        self.padding = padding

    def write(
        self,
        image_path: Path,
        asset_id: str,
        detections,
    ) -> list[tuple[int, Path]]:

        self.crop_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        image = open_upright(image_path).convert("RGB")

        width, height = image.size

        crops = []

        for index, detection in enumerate(detections):
            if detection.label not in _DETECTABLE_LABELS:
                continue

            if (
                detection.x1 < 0
                or detection.y1 < 0
                or detection.x2 > width
                or detection.y2 > height
            ):
                # Detector output is external, untrusted input -- a
                # mismatch between the detector's and Pillow's view of the
                # image's dimensions has previously produced coordinates
                # outside the actual image (see issue #88). Logging this
                # makes a recurrence diagnosable without reproducing it.
                logger.warning(
                    "Detection box outside image bounds: asset=%s image=%s "
                    "size=%dx%d label=%s confidence=%.3f box=(%d, %d, %d, %d)",
                    asset_id,
                    image_path,
                    width,
                    height,
                    detection.label,
                    detection.confidence,
                    detection.x1,
                    detection.y1,
                    detection.x2,
                    detection.y2,
                )

            box = self._expand_box(
                detection.x1,
                detection.y1,
                detection.x2,
                detection.y2,
                width,
                height,
            )

            if box[2] <= box[0] or box[3] <= box[1]:
                logger.warning(
                    "Skipping degenerate crop: asset=%s image=%s box=%s",
                    asset_id,
                    image_path,
                    box,
                )
                continue

            crop = image.crop(box)

            output = self.crop_dir / f"{asset_id}_{index}.jpg"

            crop.save(output)

            crops.append((index, output))

        return crops

    def _expand_box(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:

        # Clamp into image bounds (and sort, in case the raw box is
        # already inverted) before padding, so the padded box below can
        # never end up with its lower/right edge past its upper/left edge
        # -- Image.crop() raises ValueError when that happens.
        x1, x2 = (max(0, min(v, width)) for v in sorted((x1, x2)))
        y1, y2 = (max(0, min(v, height)) for v in sorted((y1, y2)))

        box_width = x2 - x1
        box_height = y2 - y1

        pad_x = int(box_width * self.padding)

        pad_y = int(box_height * self.padding)

        return (
            max(0, x1 - pad_x),
            max(0, y1 - pad_y),
            min(width, x2 + pad_x),
            min(height, y2 + pad_y),
        )
