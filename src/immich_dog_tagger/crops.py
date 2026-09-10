import logging
from pathlib import Path

from PIL import Image

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
        expected_size: tuple[int, int] | None = None,
    ) -> list[tuple[int, Path]]:

        self.crop_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        image = open_upright(image_path, expected_size).convert("RGB")

        crops = []

        for index, detection in enumerate(detections):
            if detection.label not in _DETECTABLE_LABELS:
                continue

            cropped = self.crop_one(
                image,
                detection.x1,
                detection.y1,
                detection.x2,
                detection.y2,
                context=f"asset={asset_id} image={image_path}",
            )

            if cropped is None:
                continue

            output = self.crop_dir / f"{asset_id}_{index}.jpg"

            cropped.save(output)

            crops.append((index, output))

        return crops

    def crop_one(
        self,
        image: Image.Image,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        context: str = "",
    ) -> Image.Image | None:
        """
        Crop and pad a single bounding box out of an already-decoded,
        upright RGB image, shared by `write()`'s per-detection loop and
        `ManualDetectionAssignmentService` (issue #261), which crops one
        detection at a time from a live-downloaded image rather than a
        batch decoded from a cached original. Returns `None` for a
        degenerate box (out of bounds or zero-area after clamping/padding)
        instead of raising, matching `write()`'s existing skip-and-log
        behavior -- callers that need to distinguish "skipped" from
        "succeeded" check for `None`.
        """
        width, height = image.size

        if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
            # Detector output is external, untrusted input -- a mismatch
            # between the detector's and Pillow's view of the image's
            # dimensions has previously produced coordinates outside the
            # actual image (see issue #88). Logging this makes a
            # recurrence diagnosable without reproducing it.
            logger.warning(
                "Detection box outside image bounds: %s size=%dx%d box=(%d, %d, %d, %d)",
                context,
                width,
                height,
                x1,
                y1,
                x2,
                y2,
            )

        box = self._expand_box(x1, y1, x2, y2, width, height)

        if box[2] <= box[0] or box[3] <= box[1]:
            logger.warning(
                "Skipping degenerate crop: %s box=%s",
                context,
                box,
            )
            return None

        return image.crop(box)

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
