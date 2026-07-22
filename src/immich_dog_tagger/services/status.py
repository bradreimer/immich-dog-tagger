from dataclasses import dataclass

from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
)


@dataclass(frozen=True)
class PipelineStats:
    assets: int
    detections: int
    crops: int
    classifications: int
    identities: int
    examples: int


class StatusService:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def summary(self) -> PipelineStats:
        return PipelineStats(
            assets=self.session.query(Asset).count(),
            detections=self.session.query(Detection).count(),
            crops=self.session.query(Crop).count(),
            classifications=self.session.query(CropClassification).count(),
            identities=self.session.query(Identity).count(),
            examples=self.session.query(EmbeddingExample).count(),
        )
