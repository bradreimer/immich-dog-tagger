from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .crops import CropWriter
from .detector import ObjectDetector
from .models import Asset, Crop, Detection
from .status import AssetStatus


@dataclass
class DetectionSummary:
    processed: int
    detections: int
    dogs: int


class DetectionService:
    def __init__(
        self,
        detector: ObjectDetector,
        session: Session,
        cache_dir: Path,
        crop_writer: CropWriter | None = None,
    ):
        self.detector = detector
        self.session = session
        self.cache_dir = cache_dir
        self.crop_writer = crop_writer

    def is_image_asset(self, asset: Asset) -> bool:
        return asset.extension.lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".tiff",
            ".bmp",
            ".gif",
            ".heic",
        }

    def run(
        self,
        limit: int | None = None,
    ) -> DetectionSummary:

        query = select(Asset).where(Asset.status == AssetStatus.DOWNLOADED)

        if limit is not None:
            query = query.limit(limit)

        assets = [
            asset
            for asset in self.session.scalars(query).all()
            if self.is_image_asset(asset)
        ]

        processed = 0
        detection_count = 0
        dog_count = 0

        for asset in assets:
            image_path = asset.cache_path(self.cache_dir)

            detections = self.detector.detect(str(image_path))

            crop_map: dict[int, Path] = {}

            if self.crop_writer:
                crop_results = self.crop_writer.write(
                    image_path,
                    asset.immich_asset_id,
                    detections,
                )

                crop_map = dict(crop_results)

            for index, detection in enumerate(detections):
                detection_count += 1

                if detection.label == "dog":
                    dog_count += 1

                db_detection = Detection(
                    asset_id=asset.id,
                    label=detection.label,
                    confidence=detection.confidence,
                    x1=detection.x1,
                    y1=detection.y1,
                    x2=detection.x2,
                    y2=detection.y2,
                )

                self.session.add(db_detection)

                self.session.flush()

                crop_path = crop_map.get(index)

                if crop_path:
                    self.session.add(
                        Crop(
                            detection_id=db_detection.id,
                            path=str(crop_path),
                        )
                    )

            asset.status = AssetStatus.DETECTED

            processed += 1

        self.session.commit()

        return DetectionSummary(
            processed=processed,
            detections=detection_count,
            dogs=dog_count,
        )
