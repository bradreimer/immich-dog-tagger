from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.detector import ObjectDetector
from immich_dog_tagger.enums import AssetStatus, Species
from immich_dog_tagger.media import is_supported_image
from immich_dog_tagger.models import Asset, Crop, Detection


@dataclass
class DetectionSummary:
    processed: int
    detections: int
    dogs: int
    cats: int


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

    def run(
        self,
        limit: int | None = None,
        force: bool = False,
    ) -> DetectionSummary:

        query = select(Asset).where(
            Asset.status == AssetStatus.DOWNLOADED,
            ~exists().where(Detection.asset_id == Asset.id),
        )

        if force:
            query = select(Asset).where(
                Asset.status.in_(
                    [
                        AssetStatus.DOWNLOADED,
                        AssetStatus.DETECTED,
                    ]
                )
            )

        if limit is not None:
            query = query.limit(limit)

        assets = self.session.scalars(query).all()

        processed = 0
        detection_count = 0
        dog_count = 0
        cat_count = 0

        for asset in assets:
            image_path = asset.cache_path(self.cache_dir)

            if not is_supported_image(image_path):
                continue

            if force:
                existing = self.session.scalars(
                    select(Detection).where(
                        Detection.asset_id == asset.id,
                    )
                ).all()

                for detection in existing:
                    if detection.crop:
                        crop_path = Path(detection.crop.path)

                        if crop_path.exists():
                            crop_path.unlink()

                    self.session.delete(detection)

                self.session.flush()

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
                elif detection.label == "cat":
                    cat_count += 1

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
                            species=Species(detection.label),
                        )
                    )

            asset.status = AssetStatus.DETECTED

            processed += 1

        self.session.commit()

        return DetectionSummary(
            processed=processed,
            detections=detection_count,
            dogs=dog_count,
            cats=cat_count,
        )
