from pydantic import BaseModel


class ClassificationResponse(BaseModel):
    classification_id: int
    crop_id: int
    identity: str | None
    confidence: float
    filename: str


class ReviewPredictionResponse(BaseModel):
    identity: str | None
    similarity: float


class ReviewSuggestionResponse(BaseModel):
    identity: str
    similarity: float
    example_id: int


class CorrectionRequest(BaseModel):
    identity: str


class ReviewItemResponse(BaseModel):
    classification_id: int
    crop_id: int
    path: str

    prediction: ReviewPredictionResponse
    suggestion: ReviewSuggestionResponse | None

    @classmethod
    def from_item(cls, item):
        return cls(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            path=str(item.path),
            prediction=ReviewPredictionResponse(
                identity=item.prediction.identity,
                similarity=item.prediction.similarity,
            ),
            suggestion=(
                ReviewSuggestionResponse(
                    identity=item.suggestion.identity,
                    similarity=item.suggestion.similarity,
                    example_id=item.suggestion.example_id,
                )
                if item.suggestion
                else None
            ),
        )


class ReviewQueueStatsResponse(BaseModel):
    total: int
    reviewed: int
    remaining: int
