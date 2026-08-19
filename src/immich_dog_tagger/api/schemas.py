from datetime import datetime

from pydantic import BaseModel

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation, Species


class ScheduleResponse(BaseModel):
    id: int
    name: str
    operation: PipelineOperation
    expression: str
    timezone_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_result: str | None

    @classmethod
    def from_schedule(cls, schedule):
        return cls(
            id=schedule.id,
            name=schedule.name,
            operation=schedule.operation,
            expression=schedule.expression,
            timezone_name=schedule.timezone_name,
            enabled=schedule.enabled,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            next_run_at=schedule.next_run_at,
            last_run_at=schedule.last_run_at,
            last_run_result=schedule.last_run_result,
        )


class ScheduleCreateRequest(BaseModel):
    name: str
    operation: PipelineOperation
    expression: str
    timezone_name: str = "UTC"
    enabled: bool = True


class ScheduleRunResponse(BaseModel):
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


class ScheduleUpdateRequest(BaseModel):
    name: str | None = None
    operation: PipelineOperation | None = None
    expression: str | None = None
    timezone_name: str | None = None
    enabled: bool | None = None


class DogResponse(BaseModel):
    id: int
    name: str
    species: Species
    active: bool

    @classmethod
    def from_identity(cls, identity):
        return cls(
            id=identity.id,
            name=identity.name,
            species=identity.species,
            active=identity.is_active,
        )


class DogCreateRequest(BaseModel):
    name: str
    species: Species = Species.DOG


class DogUpdateRequest(BaseModel):
    name: str


class DogMergeRequest(BaseModel):
    """Absorb the identity in the path into `target_id` (issue #148)."""

    target_id: int


class DogMergeResponse(BaseModel):
    source: DogResponse
    target: DogResponse
    classifications_reassigned: int
    examples_reassigned: int
    examples_discarded: int
    occurrences_reassigned: int


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


class SpeciesCorrectionRequest(BaseModel):
    species: Species


class ReviewItemResponse(BaseModel):
    classification_id: int
    crop_id: int
    image_url: str
    species: str
    captured_at: datetime | None
    immich_asset_id: str | None

    prediction: ReviewPredictionResponse
    suggestion: ReviewSuggestionResponse | None
    reason: str

    @classmethod
    def from_item(cls, item):
        return cls(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            image_url=f"/crops/{item.crop_id}",
            species=item.species,
            captured_at=item.captured_at,
            immich_asset_id=item.immich_asset_id,
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


class LibraryEntryResponse(BaseModel):
    item: ReviewItemResponse
    reviewed: bool
    reviewed_at: datetime | None

    @classmethod
    def from_entry(cls, entry):
        return cls(
            item=ReviewItemResponse.from_item(entry.item),
            reviewed=entry.reviewed,
            reviewed_at=entry.reviewed_at,
        )


class LibraryPageResponse(BaseModel):
    items: list[LibraryEntryResponse]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_page(cls, page):
        return cls(
            items=[LibraryEntryResponse.from_entry(entry) for entry in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )


class ReviewCandidateResponse(BaseModel):
    identity: str
    similarity: float
    matched_example_id: int


class JobCreateRequest(BaseModel):
    operation: PipelineOperation
    start: bool = True


class ClassificationPassResponse(BaseModel):
    id: int
    status: str
    classifier_version: str
    threshold: float
    eligible_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    changed_count: int
    labeled_example_count: int | None
    review_queue_size: int | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_summary(cls, summary):
        return cls(
            id=summary.id,
            status=summary.status,
            classifier_version=summary.classifier_version,
            threshold=summary.threshold,
            eligible_count=summary.eligible_count,
            confident_count=summary.confident_count,
            needs_review_count=summary.needs_review_count,
            unknown_count=summary.unknown_count,
            changed_count=summary.changed_count,
            labeled_example_count=summary.labeled_example_count,
            review_queue_size=summary.review_queue_size,
            error_message=summary.error_message,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
        )


class SpeciesMetricsResponse(BaseModel):
    species: str
    eligible_count: int
    confident_count: int
    unknown_count: int
    reviewed_count: int
    labeled_example_count: int
    coverage: float | None

    @classmethod
    def from_species_metrics(cls, species_metrics):
        return cls(
            species=species_metrics.species,
            eligible_count=species_metrics.eligible_count,
            confident_count=species_metrics.confident_count,
            unknown_count=species_metrics.unknown_count,
            reviewed_count=species_metrics.reviewed_count,
            labeled_example_count=species_metrics.labeled_example_count,
            coverage=species_metrics.coverage,
        )


class LearningMetricsResponse(BaseModel):
    eligible_count: int
    reviewed_count: int
    labeled_example_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    coverage: float | None
    review_rate: float | None
    unknown_rate: float | None
    review_queue_size: int
    no_review_needed_count: int
    automation_rate: float | None
    last_reclassification: ClassificationPassResponse | None
    pass_history: list[ClassificationPassResponse]
    by_species: list[SpeciesMetricsResponse]

    @classmethod
    def from_metrics(cls, metrics):
        return cls(
            eligible_count=metrics.eligible_count,
            reviewed_count=metrics.reviewed_count,
            labeled_example_count=metrics.labeled_example_count,
            confident_count=metrics.confident_count,
            needs_review_count=metrics.needs_review_count,
            unknown_count=metrics.unknown_count,
            coverage=metrics.coverage,
            review_rate=metrics.review_rate,
            unknown_rate=metrics.unknown_rate,
            review_queue_size=metrics.review_queue_size,
            no_review_needed_count=metrics.no_review_needed_count,
            automation_rate=metrics.automation_rate,
            last_reclassification=(
                ClassificationPassResponse.from_summary(metrics.last_reclassification)
                if metrics.last_reclassification
                else None
            ),
            pass_history=[
                ClassificationPassResponse.from_summary(summary)
                for summary in metrics.pass_history
            ],
            by_species=[
                SpeciesMetricsResponse.from_species_metrics(species_metrics)
                for species_metrics in metrics.by_species
            ],
        )


class JobResponse(BaseModel):
    id: int
    operation: PipelineOperation
    status: PipelineJobStatus
    progress_current: int
    progress_total: int | None
    progress_message: str | None
    error_message: str | None
    cancel_requested: bool
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
            cancel_requested=job.cancel_requested,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )


class SettingsResponse(BaseModel):
    immich_url: str
    immich_external_url: str
    scanned_image_count: int
    version: str


class PlaceCountResponse(BaseModel):
    label: str
    city: str | None
    state: str | None
    country: str | None
    count: int

    @classmethod
    def from_place_count(cls, place):
        return cls(
            label=place.label,
            city=place.city,
            state=place.state,
            country=place.country,
            count=place.count,
        )


class PersonCountResponse(BaseModel):
    label: str
    person_id: str
    name: str | None
    count: int

    @classmethod
    def from_person_count(cls, person):
        return cls(
            label=person.label,
            person_id=person.person_id,
            name=person.name,
            count=person.count,
        )


class TimelineEntryResponse(BaseModel):
    asset_id: int
    immich_asset_id: str
    captured_at: datetime | None
    city: str | None
    state: str | None
    country: str | None
    confidence: float
    source: str

    @classmethod
    def from_timeline_entry(cls, entry):
        return cls(
            asset_id=entry.asset_id,
            immich_asset_id=entry.immich_asset_id,
            captured_at=entry.captured_at,
            city=entry.city,
            state=entry.state,
            country=entry.country,
            confidence=entry.confidence,
            source=entry.source,
        )


class InsightCardResponse(BaseModel):
    slug: str
    title: str
    value: str
    subtext: str | None
    category: str

    @classmethod
    def from_card(cls, card):
        return cls(
            slug=card.slug,
            title=card.title,
            value=card.value,
            subtext=card.subtext,
            category=card.category,
        )


class InsightsSummaryResponse(BaseModel):
    identity_id: int
    identity_name: str
    total_photos: int
    first_seen: datetime | None
    last_seen: datetime | None
    photos_by_year: dict[int, int]
    top_place: PlaceCountResponse | None
    top_person: PersonCountResponse | None
    favorite_photo_count: int

    @classmethod
    def from_summary(cls, summary):
        return cls(
            identity_id=summary.identity_id,
            identity_name=summary.identity_name,
            total_photos=summary.total_photos,
            first_seen=summary.first_seen,
            last_seen=summary.last_seen,
            photos_by_year=summary.photos_by_year,
            top_place=PlaceCountResponse.from_place_count(summary.top_place)
            if summary.top_place
            else None,
            top_person=PersonCountResponse.from_person_count(summary.top_person)
            if summary.top_person
            else None,
            favorite_photo_count=summary.favorite_photo_count,
        )
