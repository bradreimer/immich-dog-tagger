from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .detector import ObjectDetector
from .models import Asset, Detection
from .status import AssetStatus


class DetectionService:
    def __init__(
        self,
        detector: ObjectDetector,
        session: Session,
        cache_dir: Path,
    ):
        self.detector = detector
        self.session = session
        self.cache_dir = cache_dir

    def run(
        self,
        limit: int | None = None,
    ) -> int:

        query = (
            select(Asset)
            .where(
                Asset.status == AssetStatus.DOWNLOADED
            )
        )

        if limit is not None:
            query = query.limit(limit)

        assets = self.session.scalars(query).all()

        processed = 0

        for asset in assets:

            image_path = asset.cache_path(self.cache_dir)

            detections = self.detector.detect(
                str(image_path)
            )

            for detection in detections:
                self.session.add(
                    Detection(
                        asset_id=asset.id,
                        label=detection.label,
                        confidence=detection.confidence,
                        x1=detection.x1,
                        y1=detection.y1,
                        x2=detection.x2,
                        y2=detection.y2,
                    )
                )

            asset.status = AssetStatus.DETECTED

            processed += 1

        self.session.commit()

        return processed