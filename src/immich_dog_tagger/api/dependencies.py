from collections.abc import Generator
from functools import cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.config import load_config
from immich_dog_tagger.database import create_database
from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.runtime import get_embedder
from immich_dog_tagger.services.app_settings import AutoReclassifyService
from immich_dog_tagger.services.clusters import (
    ClusterApprovalService,
    RecommendationClusterService,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.dogs import DogService
from immich_dog_tagger.services.insights import InsightsService
from immich_dog_tagger.services.job_dispatcher import PipelineJobDispatcher
from immich_dog_tagger.services.job_execution import create_pipeline_job_runner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.rejections import RejectionService
from immich_dog_tagger.services.review_actions import ReviewActionService
from immich_dog_tagger.services.review_query import ReviewQueryService
from immich_dog_tagger.services.schedules import (
    PipelineScheduleRepository,
    PipelineScheduleService,
)


@cache
def get_engine():
    config = load_config()

    return create_database(
        config.state_dir,
    )


@cache
def get_config():
    return load_config()


def get_session() -> Generator[Session]:
    engine = get_engine()

    with Session(engine) as session:
        yield session


def get_job_repository(
    session: Annotated[Session, Depends(get_session)],
) -> PipelineJobRepository:
    return PipelineJobRepository(session)


def get_job_service(
    session: Annotated[Session, Depends(get_session)],
) -> PipelineJobService:
    return PipelineJobService(session)


def get_schedule_repository(
    session: Annotated[Session, Depends(get_session)],
) -> PipelineScheduleRepository:
    return PipelineScheduleRepository(session)


def get_schedule_service(
    session: Annotated[Session, Depends(get_session)],
) -> PipelineScheduleService:
    return PipelineScheduleService(session)


@cache
def get_job_dispatcher() -> PipelineJobDispatcher:
    config = load_config()

    def runner_factory(session: Session):
        return create_pipeline_job_runner(
            session,
            config,
        )

    return PipelineJobDispatcher(
        engine_factory=get_engine,
        runner_factory=runner_factory,
    )


def get_review_query_service(
    session: Annotated[Session, Depends(get_session)],
) -> ReviewQueryService:
    return ReviewQueryService(session)


def get_dog_service(
    session: Annotated[Session, Depends(get_session)],
) -> DogService:
    return DogService(session)


def get_review_action_service(
    session: Annotated[Session, Depends(get_session)],
) -> ReviewActionService:
    return ReviewActionService(session)


def get_insights_service(
    session: Annotated[Session, Depends(get_session)],
) -> InsightsService:
    return InsightsService(session)


def get_correction_service(
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> ClassificationCorrectionService:
    learner = Learner(
        embedder=embedder,
        session=session,
    )

    return ClassificationCorrectionService(
        session=session,
        learner=learner,
        classifier=IdentityClassifier(session),
    )


def get_cluster_service(
    session: Annotated[Session, Depends(get_session)],
) -> RecommendationClusterService:
    return RecommendationClusterService(session)


def get_rejection_service(
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> RejectionService:
    learner = Learner(
        embedder=embedder,
        session=session,
    )

    return RejectionService(
        session=session,
        learner=learner,
        classifier=IdentityClassifier(session),
    )


def get_cluster_approval_service(
    session: Annotated[Session, Depends(get_session)],
    correction_service: Annotated[
        ClassificationCorrectionService,
        Depends(get_correction_service),
    ],
    rejection_service: Annotated[
        RejectionService,
        Depends(get_rejection_service),
    ],
) -> ClusterApprovalService:
    return ClusterApprovalService(
        session=session,
        correction_service=correction_service,
        rejection_service=rejection_service,
    )


def get_auto_reclassify_service(
    session: Annotated[Session, Depends(get_session)],
    job_service: Annotated[PipelineJobService, Depends(get_job_service)],
) -> AutoReclassifyService:
    return AutoReclassifyService(session, job_service)
