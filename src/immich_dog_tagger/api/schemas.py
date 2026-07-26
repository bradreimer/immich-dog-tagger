from pydantic import BaseModel


class ClassificationResponse(BaseModel):
    classification_id: int
    crop_id: int
    identity: str | None
    confidence: float
    filename: str


class ReviewItemResponse(BaseModel):
    classification_id: int
    crop_id: int
    identity: str | None
    confidence: float
    path: str
    matched_example_path: str | None

    @classmethod
    def from_item(
        cls,
        item,
    ):
        return cls(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            identity=item.identity,
            confidence=item.confidence,
            path=str(item.path),
            matched_example_path=(
                str(item.matched_example_path) if item.matched_example_path else None
            ),
        )


class CorrectionRequest(BaseModel):
    identity: str
