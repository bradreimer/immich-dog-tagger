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
    example_path: str


class PredictionResponse(BaseModel):
    identity: str | None
    similarity: float


class CorrectionRequest(BaseModel):
    identity: str


class SuggestionResponse(BaseModel):
    identity: str
    similarity: float
    example_path: str


class ReviewItemResponse(BaseModel):
    classification_id: int
    crop_id: int
    path: str

    prediction: PredictionResponse
    suggestion: SuggestionResponse | None

    @classmethod
    def from_item(cls, item):
        return cls(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            path=str(item.path),
            prediction=PredictionResponse(
                identity=item.prediction.identity,
                similarity=item.prediction.similarity,
            ),
            suggestion=(
                SuggestionResponse(
                    identity=item.suggestion.identity,
                    similarity=item.suggestion.similarity,
                    example_path=str(item.suggestion.example_path),
                )
                if item.suggestion
                else None
            ),
        )
