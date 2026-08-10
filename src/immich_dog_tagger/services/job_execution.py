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
    operation_options: dict[PipelineOperation, dict] | None = None,
) -> PipelineJobRunner:
    repository = PipelineJobRepository(session)
    service = PipelineJobService(session, repository=repository)

    options = operation_options or {}

    handlers = {
        PipelineOperation.SCAN: _scan_handler(
            session,
            config,
            options.get(PipelineOperation.SCAN, {}),
        ),
        PipelineOperation.DETECT: _detect_handler(
            session,
            config,
            options.get(PipelineOperation.DETECT, {}),
        ),
        PipelineOperation.EMBED: _embed_handler(
            session,
            options.get(PipelineOperation.EMBED, {}),
        ),
        PipelineOperation.CLASSIFY: _classify_handler(
            session,
            options.get(PipelineOperation.CLASSIFY, {}),
        ),
        PipelineOperation.LEARN: _learn_handler(
            session,
            options.get(PipelineOperation.LEARN, {}),
        ),
        PipelineOperation.SYNC: _sync_handler(
            session,
            config,
            options.get(PipelineOperation.SYNC, {}),
        ),
        PipelineOperation.FULL_PIPELINE: _full_pipeline_handler(
            session,
            config,
            options.get(PipelineOperation.FULL_PIPELINE, {}),
        ),
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


def _scan_handler(
    session: Session,
    config: Config,
    options: dict,
):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Scanning Immich")

        scanner = Scanner(
            _create_client(config),
            session,
        )
        scanned = scanner.scan(
            limit=options.get("limit"),
            force=options.get("force", False),
        )

        progress.message(f"Scanned {scanned} assets")
        return {"scanned": scanned}

    return run


def _detect_handler(
    session: Session,
    config: Config,
    options: dict,
):
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

        summary = service.run(
            limit=options.get("limit"),
            force=options.get("force", False),
        )

        progress.message(f"Detected {summary.dogs} dogs")
        return {
            "processed": summary.processed,
            "detections": summary.detections,
            "dogs": summary.dogs,
        }

    return run


def _embed_handler(
    session: Session,
    options: dict,
):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        pending_crops = session.scalars(
            select(Crop).where(~Crop.classification.has())
        ).all()

        limit = options.get("limit")
        if limit is not None:
            pending_crops = pending_crops[:limit]

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


def _classify_handler(
    session: Session,
    options: dict,
):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Classifying crops")

        embedder = get_embedder()
        classifier = ClassificationService(
            session,
            embedder,
            IdentityClassifier(session),
        )

        summary = classifier.classify(
            mode=options.get("mode", ClassificationMode.PENDING),
            limit=options.get("limit"),
            threshold=options.get("threshold", 0.80),
        )

        progress.message(f"Classified {summary.classified} crops")
        return {
            "classified": summary.classified,
            "identities": summary.identities,
        }

    return run


def _learn_handler(
    session: Session,
    options: dict,
):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        identity_name = options.get("identity")
        directory = options.get("directory")

        if identity_name and directory:
            embedder = get_embedder()
            learner = Learner(
                embedder,
                session,
            )

            summary = learner.learn(
                identity_name,
                Path(directory),
            )

            progress.set(
                current=1,
                total=1,
                message=f"Learned {identity_name}",
            )

            return {
                "identities": 1,
                "imported": summary.imported,
            }

        reference_root = Path(options.get("reference_root", "references"))
        if (
            not reference_root.exists()
            and "reference_root" not in options
            and Path("training").exists()
        ):
            # Backward compatibility for existing deployments using ./training.
            reference_root = Path("training")

        if not reference_root.exists():
            raise ValueError("reference directory not found")

        embedder = get_embedder()
        learner = Learner(
            embedder,
            session,
        )

        identities = [
            path for path in sorted(reference_root.iterdir()) if path.is_dir()
        ]

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


def _sync_handler(
    session: Session,
    config: Config,
    options: dict,
):
    def run(progress: JobProgressReporter) -> dict[str, int]:
        progress.message("Synchronizing albums")

        service = SyncService(
            session,
            AlbumService(_create_client(config)),
        )
        summary = service.sync(
            dry_run=options.get("dry_run", False),
        )

        progress.message(f"Synchronized {len(summary.identities)} identities")
        return {
            "identities": len(summary.identities),
            "items": [
                {
                    "identity": item.identity,
                    "assets": item.assets,
                }
                for item in summary.identities
            ],
        }

    return run


def _full_pipeline_handler(
    session: Session,
    config: Config,
    options: dict,
):
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

        progress_callback = options.get("progress_callback")

        def report(message: str) -> None:
            progress.message(message)

            if progress_callback is not None:
                progress_callback(message)

        summary = pipeline.run(
            progress=report,
            limit=options.get("limit"),
            force=options.get("force", False),
        )

        return {
            "scanned": summary.scanned,
            "downloaded": summary.downloaded,
            "detected": summary.detected,
            "classified": summary.classified,
        }

    return run
