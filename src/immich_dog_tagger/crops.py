from pathlib import Path

from PIL import Image


class CropWriter:
    def __init__(
        self,
        crop_dir: Path,
    ):
        self.crop_dir = crop_dir

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

        count = 0

        for index, detection in enumerate(detections):

            if detection.label != "dog":
                continue

            crop = image.crop(
                (
                    detection.x1,
                    detection.y1,
                    detection.x2,
                    detection.y2,
                )
            )

            output = (
                self.crop_dir
                / f"{asset_id}_{index}.jpg"
            )

            crop.save(output)

            count += 1

        return count