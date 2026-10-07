from collections.abc import Generator
from functools import cache
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.config import Config, load_config
from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.database import create_database
from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.embedder import Embedder
from immich_dog_tagger.immich import ImmichClient
from immich_dog_tagger.runtime import get_embedder, get_yolo_detector
from immich_dog_tagger.services.accounts import (
    AccountResolutionError,
    ResolvedAccount,
    resolve_account,
    resolve_asset_account,
)
from immich_dog_tagger.services.app_settings import (
    AppSettingsService,
    AutoReclassifyService,
)
from immich_dog_tagger.services.asset_repair import AssetRepairService
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.services.clusters import (
    ClusterApprovalService,
    ConfirmedClusterService,
    RecommendationClusterService,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.derived_data import DerivedDataService
from immich_dog_tagger.services.detection import DetectionService
from immich_dog_tagger.services.dogs import DogService
from immich_dog_tagger.services.false_positives import FalsePositiveService
from immich_dog_tagger.services.insights import InsightsService
from immich_dog_tagger.services.job_dispatcher import PipelineJobDispatcher
from immich_dog_tagger.services.job_execution import create_pipeline_job_runner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.manual_detection_assignment import (
    ManualDetectionAssignmentService,
)
from immich_dog_tagger.services.photo_lookup import PhotoLookupService
from immich_dog_tagger.services.rejections import RejectionService
from immich_dog_tagger.services.review_actions import ReviewActionService
from immich_dog_tagger.services.review_groups import ReviewGroupingService
from immich_dog_tagger.services.review_query import ReviewQueryService
from immich_dog_tagger.services.schedules import (
    PipelineScheduleRepository,
    PipelineScheduleService,
)
from immich_dog_tagger.services.stale_detection import StaleDetectionService


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
    return ReviewQueryService(session, policy=AppSettingsService(session).policy())


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


def get_confirmed_cluster_service(
    session: Annotated[Session, Depends(get_session)],
) -> ConfirmedClusterService:
    return ConfirmedClusterService(session)


def get_review_grouping_service(
    session: Annotated[Session, Depends(get_session)],
) -> ReviewGroupingService:
    # Same effective policy Queue mode's active_review() uses (issue #341),
    # so Grouped mode pools exactly the items Queue mode would also
    # consider "needs review" -- not every unreviewed classification.
    return ReviewGroupingService(session, policy=AppSettingsService(session).policy())


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
    dispatcher: Annotated[PipelineJobDispatcher, Depends(get_job_dispatcher)],
) -> AutoReclassifyService:
    return AutoReclassifyService(session, job_service, dispatcher)


def get_photo_lookup_service(
    session: Annotated[Session, Depends(get_session)],
) -> PhotoLookupService:
    return PhotoLookupService(session)


def get_false_positive_service(
    session: Annotated[Session, Depends(get_session)],
    correction_service: Annotated[
        ClassificationCorrectionService,
        Depends(get_correction_service),
    ],
) -> FalsePositiveService:
    return FalsePositiveService(session, correction_service)


@cache
def get_immich_client() -> ImmichClient:
    config = load_config()

    return ImmichClient(
        config.immich_url,
        config.immich_api_key,
        timeout=config.immich_timeout_seconds,
    )


@cache
def _account_client(url: str, api_key: str, timeout: float) -> ImmichClient:
    return ImmichClient(url, api_key, timeout=timeout)


def get_asset_account(
    immich_asset_id: str,
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
) -> ResolvedAccount:
    """The account owning the photo in the request path (see resolve_asset_account)."""
    try:
        return resolve_asset_account(session, config, immich_asset_id)
    except AccountResolutionError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Can't reach this photo's Immich account: {e}",
        ) from e


def get_asset_immich_client(
    account: Annotated[ResolvedAccount, Depends(get_asset_account)],
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
    default_client: Annotated[ImmichClient, Depends(get_immich_client)],
) -> ImmichClient:
    """Client holding the API key of the account that owns the requested photo."""
    if account.api_key == resolve_account(session, config, None).api_key:
        return default_client

    return _account_client(
        config.immich_url, account.api_key, config.immich_timeout_seconds
    )


def _build_asset_repair_service(
    session: Session,
    config: Config,
    client: ImmichClient,
    embedder: Embedder,
    account_id: int | None,
) -> AssetRepairService:
    policy = AppSettingsService(session).policy()

    return AssetRepairService(
        session,
        Downloader(client, session, config.cache_dir),
        DetectionService(
            get_yolo_detector(),
            session,
            config.cache_dir,
            CropWriter(config.crop_dir, config.crop_padding),
        ),
        ClassificationService(
            session,
            embedder,
            IdentityClassifier(session, policy=policy),
            policy=policy,
        ),
        account_id=account_id,
    )


def get_asset_repair_service(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
    client: Annotated[ImmichClient, Depends(get_immich_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> AssetRepairService:
    # Library-wide callers (diagnostics) repair many photos through one
    # service, so this one holds the default account's API key (issue #370):
    # only that account's photos may be marked removed on a "not found".
    return _build_asset_repair_service(
        session,
        config,
        client,
        embedder,
        resolve_account(session, config, None).id,
    )


def get_photo_asset_repair_service(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
    account: Annotated[ResolvedAccount, Depends(get_asset_account)],
    client: Annotated[ImmichClient, Depends(get_asset_immich_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> AssetRepairService:
    """Repair for the one photo in the request path, using its owning account."""
    return _build_asset_repair_service(session, config, client, embedder, account.id)


def _build_manual_detection_assignment_service(
    session: Session,
    config: Config,
    client: ImmichClient,
    embedder: Embedder,
    correction_service: ClassificationCorrectionService,
    false_positive_service: FalsePositiveService,
) -> ManualDetectionAssignmentService:
    return ManualDetectionAssignmentService(
        session=session,
        client=client,
        embedder=embedder,
        crop_writer=CropWriter(config.crop_dir, config.crop_padding),
        correction_service=correction_service,
        false_positive_service=false_positive_service,
    )


def get_manual_detection_assignment_service(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
    client: Annotated[ImmichClient, Depends(get_immich_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    correction_service: Annotated[
        ClassificationCorrectionService,
        Depends(get_correction_service),
    ],
    false_positive_service: Annotated[
        FalsePositiveService,
        Depends(get_false_positive_service),
    ],
) -> ManualDetectionAssignmentService:
    return _build_manual_detection_assignment_service(
        session, config, client, embedder, correction_service, false_positive_service
    )


def get_photo_manual_detection_assignment_service(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
    client: Annotated[ImmichClient, Depends(get_asset_immich_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    correction_service: Annotated[
        ClassificationCorrectionService,
        Depends(get_correction_service),
    ],
    false_positive_service: Annotated[
        FalsePositiveService,
        Depends(get_false_positive_service),
    ],
) -> ManualDetectionAssignmentService:
    """Manual assignment for the photo in the request path, using its owning account."""
    return _build_manual_detection_assignment_service(
        session, config, client, embedder, correction_service, false_positive_service
    )


def get_stale_detection_service(
    session: Annotated[Session, Depends(get_session)],
) -> StaleDetectionService:
    return StaleDetectionService(session)


def get_derived_data_service(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
) -> DerivedDataService:
    return DerivedDataService(session, config.cache_dir)
