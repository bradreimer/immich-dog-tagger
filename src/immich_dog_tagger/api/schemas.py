from datetime import datetime

from pydantic import BaseModel

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation


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


class JobCreateRequest(BaseModel):
    operation: PipelineOperation
    start: bool = True


class JobResponse(BaseModel):
    id: int
    operation: PipelineOperation
    status: PipelineJobStatus
    progress_current: int
    progress_total: int | None
    progress_message: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_job(cls, job):
        return cls(
            id=job.id,
            operation=job.operation,
            status=job.status,
            progress_current=job.progress_current,
            progress_total=job.progress_total,
            progress_message=job.progress_message,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
