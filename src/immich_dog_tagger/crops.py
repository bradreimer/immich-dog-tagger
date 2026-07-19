from pathlib import Path

from PIL import Image


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
    ) -> int:

        self.crop_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        image = Image.open(image_path)

        width, height = image.size

        count = 0

        for index, detection in enumerate(detections):
            if detection.label != "dog":
                continue

            box = self._expand_box(
                detection.x1,
                detection.y1,
                detection.x2,
                detection.y2,
                width,
                height,
            )

            crop = image.crop(box)

            output = self.crop_dir / f"{asset_id}_{index}.jpg"

            crop.save(output)

            count += 1

        return count

    def _expand_box(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:

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
