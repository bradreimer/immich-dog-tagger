from datetime import datetime

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
    candidates: list[ReviewCandidateResponse]


class ReviewSuggestionResponse(BaseModel):
    identity: str
    similarity: float
    example_id: int
    example_path: str
    captured_at: datetime | None


class CorrectionRequest(BaseModel):
    identity: str


class ReviewItemResponse(BaseModel):
    classification_id: int
    crop_id: int
    image_url: str

    prediction: ReviewPredictionResponse
    suggestion: ReviewSuggestionResponse | None
    reason: str

    @classmethod
    def from_item(cls, item):
        return cls(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            image_url=f"/crops/{item.crop_id}",
            prediction=ReviewPredictionResponse(
                identity=item.prediction.identity,
                similarity=item.prediction.similarity,
                candidates=[
                    ReviewCandidateResponse(
                        identity=candidate.identity,
                        similarity=candidate.similarity,
                        matched_example_id=candidate.matched_example_id,
                    )
                    for candidate in item.prediction.candidates
                ],
            ),
            suggestion=(
                ReviewSuggestionResponse(
                    identity=item.suggestion.identity,
                    similarity=item.suggestion.similarity,
                    example_id=item.suggestion.example_id,
                    example_path=str(item.suggestion.example_path),
                    captured_at=item.suggestion.captured_at,
                )
                if item.suggestion
                else None
            ),
            reason=item.reason,
        )


class ReviewQueueStatsResponse(BaseModel):
    total: int
    reviewed: int
    remaining: int


class ReviewCandidateResponse(BaseModel):
    identity: str
    similarity: float
    matched_example_id: int
