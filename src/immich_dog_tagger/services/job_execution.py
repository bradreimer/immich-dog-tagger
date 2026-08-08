from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.config import Config
from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.enums import ClassificationMode, PipelineOperation
from immich_dog_tagger.immich import ImmichClient
from immich_dog_tagger.models import Crop
from immich_dog_tagger.runtime import get_embedder
from immich_dog_tagger.scanner import Scanner
from immich_dog_tagger.services.albums import AlbumService
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.services.detection import DetectionService
from immich_dog_tagger.services.job_runner import JobProgressReporter, PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.pipeline import PipelineService
from immich_dog_tagger.services.sync import SyncService
from immich_dog_tagger.yolo_detector import YOLODetector


def create_pipeline_job_runner(
    session: Session,
    config: Config,
) -> PipelineJobRunner:
    repository = PipelineJobRepository(session)
    service = PipelineJobService(session, repository=repository)

    handlers = {
        PipelineOperation.SCAN: _scan_handler(session, config),
        PipelineOperation.DETECT: _detect_handler(session, config),
        PipelineOperation.EMBED: _embed_handler(session),
        PipelineOperation.CLASSIFY: _classify_handler(session),
        PipelineOperation.LEARN: _learn_handler(session),
        PipelineOperation.SYNC: _sync_handler(session, config),
        PipelineOperation.FULL_PIPELINE: _full_pipeline_handler(session, config),
    }

    return PipelineJobRunner(
        repository=repository,
        service=service,
        handlers=handlers,
    )


def _create_client(config: Config) -> ImmichClient:
    return ImmichClient(
        config.immich_url,
        config.immich_api_key,
    )


def _scan_handler(session: Session, config: Config):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Scanning Immich")

        scanner = Scanner(
            _create_client(config),
            session,
        )
        scanned = scanner.scan()

        progress.message(f"Scanned {scanned} assets")
        return {"scanned": scanned}

    return run


def _detect_handler(session: Session, config: Config):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Detecting dogs")

        detector = YOLODetector(config.yolo_model)
        service = DetectionService(
            detector,
            session,
            config.cache_dir,
            CropWriter(
                config.crop_dir,
                config.crop_padding,
            ),
        )

        summary = service.run()

        progress.message(f"Detected {summary.dogs} dogs")
        return {
            "processed": summary.processed,
            "dogs": summary.dogs,
        }

    return run


def _embed_handler(session: Session):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        pending_crops = session.scalars(
            select(Crop).where(~Crop.classification.has())
        ).all()

        total = len(pending_crops)
        progress.set(
            current=0,
            total=total,
            message="Embedding pending crops",
        )

        if total == 0:
            return {"embedded": 0}

        embedder = get_embedder()
        embedder.embed_batch([crop.path for crop in pending_crops])

        progress.set(
            current=total,
            message=f"Embedded {total} crops",
        )

        return {"embedded": total}

    return run


def _classify_handler(session: Session):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Classifying crops")

        embedder = get_embedder()
        classifier = ClassificationService(
            session,
            embedder,
            IdentityClassifier(session),
        )

        summary = classifier.classify(
            mode=ClassificationMode.PENDING,
        )

        progress.message(f"Classified {summary.classified} crops")
        return {
            "classified": summary.classified,
        }

    return run


def _learn_handler(session: Session):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        training_root = Path("training")

        if not training_root.exists():
            raise ValueError("training directory not found")

        embedder = get_embedder()
        learner = Learner(
            embedder,
            session,
        )

        identities = [path for path in sorted(training_root.iterdir()) if path.is_dir()]

        progress.set(
            current=0,
            total=len(identities),
            message="Learning identities",
        )

        imported = 0

        for index, identity_dir in enumerate(identities, start=1):
            summary = learner.learn(
                identity_dir.name,
                identity_dir,
            )
            imported += summary.imported

            progress.set(
                current=index,
                message=f"Learned {identity_dir.name}",
            )

        return {
            "identities": len(identities),
            "imported": imported,
        }

    return run


def _sync_handler(session: Session, config: Config):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Synchronizing albums")

        service = SyncService(
            session,
            AlbumService(_create_client(config)),
        )
        summary = service.sync(dry_run=False)

        progress.message(f"Synchronized {len(summary.identities)} identities")
        return {
            "identities": len(summary.identities),
        }

    return run


def _full_pipeline_handler(session: Session, config: Config):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        client = _create_client(config)

        pipeline = PipelineService(
            Scanner(client, session),
            Downloader(client, session, config.cache_dir),
            DetectionService(
                YOLODetector(config.yolo_model),
                session,
                config.cache_dir,
                CropWriter(
                    config.crop_dir,
                    config.crop_padding,
                ),
            ),
            ClassificationService(
                session,
                get_embedder(),
                IdentityClassifier(session),
            ),
        )

        summary = pipeline.run(
            progress=lambda message: progress.message(message),
        )

        return {
            "scanned": summary.scanned,
            "downloaded": summary.downloaded,
            "detected": summary.detected,
            "classified": summary.classified,
        }

    return run
