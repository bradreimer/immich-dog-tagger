"""
Command line interface for Immich Dog Tagger.
"""

import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from .classifier import IdentityClassifier
from .config import load_config
from .crops import CropWriter
from .database import create_database
from .downloader import Downloader
from .enums import ClassificationMode
from .immich import ImmichClient
from .review_export import ReviewExporter
from .review_import import ReviewImporter
from .runtime import get_embedder
from .scanner import Scanner
from .services.albums import AlbumService
from .services.classification import ClassificationService
from .services.correction import ClassificationCorrectionService
from .services.detection import DetectionService
from .services.learner import Learner
from .services.pipeline import PipelineService
from .services.review_query import ReviewQueryService
from .services.status import PipelinePlan, StatusService
from .services.sync import SyncService
from .yolo_detector import YOLODetector


def config_check_command(args) -> None:
    config = load_config()

    print("Immich:")
    print(f"  URL: {config.immich_url}")

    if config.immich_api_key:
        print("  API key: configured")
    else:
        print("  API key: missing")

    print()
    print("Storage:")
    print(f"  State directory: {config.state_dir}")


def init_db_command(args) -> None:
    config = load_config()

    create_database(config.state_dir)

    print(f"Database initialized: {config.state_dir / 'state.db'}")


def test_immich_command(args) -> None:
    config = load_config()

    client = ImmichClient(
        config.immich_url,
        config.immich_api_key,
    )

    assets = client.list_assets()

    print(f"Found {len(assets)} assets")


def scan_command(args) -> None:
    config = load_config()

    client = ImmichClient(
        config.immich_url,
        config.immich_api_key,
    )

    engine = create_database(config.state_dir)

    with Session(engine) as session:
        scanner = Scanner(
            client,
            session,
        )

        count = scanner.scan()

    print(f"New assets: {count}")


def download_command(args) -> None:
    config = load_config()

    client = ImmichClient(
        config.immich_url,
        config.immich_api_key,
    )

    engine = create_database(config.state_dir)

    with Session(engine) as session:
        downloader = Downloader(
            client,
            session,
            config.cache_dir,
        )

        count = downloader.download_pending(
            limit=args.limit,
        )

    print(f"Downloaded: {count}")


def detect_command(args) -> None:
    config = load_config()

    detector = YOLODetector(
        config.yolo_model,
    )

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
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
            limit=args.limit,
        )

        print(f"Processed: {summary.processed}")
        print(f"Detections: {summary.detections}")
        print(f"Dogs: {summary.dogs}")


def classify_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    embedder = get_embedder()

    with Session(engine) as session:
        classifier = IdentityClassifier(session)

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        mode = ClassificationMode.ALL if args.all else ClassificationMode.PENDING

        summary = service.classify(
            limit=args.limit,
            threshold=args.threshold,
            mode=mode,
        )

    print(f"Classified: {summary.classified}")

    for identity, count in summary.identities.items():
        print(f"{identity}: {count}")


def test_embedding_command(args) -> None:
    embedder = get_embedder()

    embedding = embedder.embed(Path(args.image))

    print(f"Dimensions: {embedding.shape[0]}")
    print(f"First values: {embedding[:5]}")


def learn_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    embedder = get_embedder()

    with Session(engine) as session:
        learner = Learner(
            embedder,
            session,
        )

        count = learner.learn(
            args.identity,
            Path(args.directory),
        )

    print(f"Learned examples: {count}")


def classify_list_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        service = ReviewQueryService(session)

        classifications = service.classifications(
            limit=args.limit,
            identity=args.identity,
            unknown=args.unknown,
        )

    print(f"{'ID':<8}{'Identity':<12}{'Similarity':<14}{'File':<40}Match")

    for item in classifications:
        print(
            f"{item.classification_id:<8}"
            f"{str(item.prediction.identity or 'Unknown'):<12}"
            f"{item.prediction.similarity:<14.4f}"
            f"{item.filename:<40}"
            f"{item.matched_example_path or ''}"
        )


def review_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        service = ReviewQueryService(session)
        summary = service.summary()

    print(f"Total classifications: {summary.total}")
    print()

    print("Identity")
    print("--------")

    for identity, count in sorted(summary.identities.items()):
        print(f"{identity:<12}{count}")

    print(f"{'Unknown':<12}{summary.unknown}")

    print()
    print("Confidence")
    print("----------")

    for bucket, count in summary.confidence_buckets.items():
        print(f"{bucket:<12}{count}")


def export_review_command(args) -> None:
    config = load_config()

    engine = create_database(config.state_dir)

    with Session(engine) as session:
        review = ReviewQueryService(session)

        items = review.classifications(
            limit=args.limit,
        )

    exporter = ReviewExporter()

    count = exporter.export(
        items,
        config.cache_dir / "review",
    )

    print(f"Exported: {count}")


def import_review_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    embedder = get_embedder()

    with Session(engine) as session:
        learner = Learner(
            embedder,
            session,
        )

        importer = ReviewImporter(
            learner,
        )

        if args.dry_run:
            plan = importer.plan_import(
                config.cache_dir / "review" / "confirmed",
            )

            print("Would import:")

            for identity, count in plan.identities.items():
                print(f"{identity}: {count}")

            print()
            print(f"Total: {plan.total}")

        else:
            summary = importer.import_confirmed(
                config.cache_dir / "review" / "confirmed",
            )

            print(f"Imported: {summary.imported}")

            for identity, count in summary.identities.items():
                print(f"{identity}: {count}")


def active_review_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        review = ReviewQueryService(session)

        items = review.active_review(
            threshold=args.threshold,
        )

    exporter = ReviewExporter()

    count = exporter.export(
        items,
        config.cache_dir / "review" / "active",
    )

    print(f"Exported: {count}")


def review_apply_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    embedder = get_embedder()

    with Session(engine) as session:
        learner = Learner(
            embedder,
            session,
        )

        correction = ClassificationCorrectionService(
            session,
            learner,
        )

        correction.correct(
            args.classification_id,
            args.identity,
        )

        session.commit()

    print(f"Applied review: {args.classification_id} -> {args.identity}")


def status_command(args) -> None:
    config = load_config()

    engine = create_database(config.state_dir)

    with Session(engine) as session:
        service = StatusService(session)
        summary = service.summary()

    print(f"Assets:             {summary.assets}")
    print(f"Detections:         {summary.detections}")
    print(f"Crops:              {summary.crops}")
    print(f"Classifications:    {summary.classifications}")
    print(f"Identities:         {summary.identities}")
    print(f"Embedding examples: {summary.examples}")
    print(f"Unknown:            {summary.unknown}")
    print(f"Low confidence:     {summary.low_confidence}")

    if args.verbose:
        print()

        print("Failures")
        print("--------")
        print(f"Download failures:          {summary.download_failed}")
        print(f"Detection failures:         {summary.detection_failed}")
        print(f"Classification failures:    {summary.classification_failed}")

        diagnostics = service.diagnostics()
        print()
        print("Diagnostics")
        print("-----------")
        for key, value in diagnostics.items():
            print(f"{key}:\t{value}")


def sync_command(args) -> None:
    config = load_config()

    client = ImmichClient(
        config.immich_url,
        config.immich_api_key,
    )

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        service = SyncService(
            session,
            AlbumService(client),
        )

        summary = service.sync(
            dry_run=args.dry_run,
        )

    if args.dry_run:
        print("Would sync:")

    for item in summary.identities:
        print(f"{item.identity}: {item.assets}")


def pipeline_command(args) -> None:
    config = load_config()

    client = ImmichClient(
        config.immich_url,
        config.immich_api_key,
    )

    engine = create_database(
        config.state_dir,
    )

    detector = YOLODetector(
        config.yolo_model,
    )

    embedder = get_embedder()

    with Session(engine) as session:
        scanner = Scanner(
            client,
            session,
        )

        downloader = Downloader(
            client,
            session,
            config.cache_dir,
        )

        detection_service = DetectionService(
            detector,
            session,
            config.cache_dir,
            CropWriter(
                config.crop_dir,
                config.crop_padding,
            ),
        )

        classifier = ClassificationService(
            session,
            embedder,
            IdentityClassifier(session),
        )

        pipeline = PipelineService(
            scanner,
            downloader,
            detection_service,
            classifier,
        )

        if args.dry_run:
            status = StatusService(session)
            plan = status.pipeline_plan()

            print("Pipeline dry run")
            print()

            def print_pipeline_plan(plan: PipelinePlan, limit: int | None) -> None:
                if plan.pending_download:
                    print(f"Would download {plan.pending_download} assets")
                else:
                    print("No pending downloads")

                if plan.pending_detection:
                    print(f"Would detect dogs in {plan.pending_detection} assets")
                else:
                    print("No pending detections")

                if plan.pending_classification:
                    print(f"Would classify {plan.pending_classification} crops")
                else:
                    print("No pending classifications")

                if limit:
                    print()
                    print(f"Limit: {limit} items per stage")

            print_pipeline_plan(plan, args.limit)

            print()
            print("No changes made.")
            return

        summary = pipeline.run(
            progress=lambda message: print(message, flush=True),
            limit=args.limit,
            force=args.force,
        )

    print("Pipeline complete")
    print()

    print("Summary")
    print("-------")
    print(f"Assets scanned:     {summary.scanned}")
    print(f"Downloaded:         {summary.downloaded}")
    print(f"Dogs detected:      {summary.detected}")
    print(f"Classified:         {summary.classified}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="immich-dog-tagger",
        description="AI-assisted dog detection and tagging for Immich",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "scan",
        help="Scan Immich for new assets",
    )

    subparsers.add_parser(
        "config-check",
        help="Display loaded configuration",
    )

    subparsers.add_parser(
        "init-db",
        help="Initialize local state database",
    )

    subparsers.add_parser(
        "test-immich",
        help="Test Immich connection",
    )

    download_parser = subparsers.add_parser(
        "download",
        help="Download pending assets",
    )

    download_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of assets to download",
    )

    detect_parser = subparsers.add_parser(
        "detect",
        help="Run dog detection",
    )

    detect_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of images to process",
    )

    classify_parser = subparsers.add_parser(
        "classify",
        help="Classify dog crops",
    )

    classify_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of crops to classify",
    )

    classify_parser.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Minimum confidence required for identity assignment",
    )

    classify_parser.add_argument(
        "--all",
        action="store_true",
        help="Reclassify already classified crops",
    )

    test_embedding_parser = subparsers.add_parser(
        "test-embedding",
        help="Generate an image embedding",
    )

    test_embedding_parser.add_argument(
        "image",
    )

    learn_parser = subparsers.add_parser(
        "learn",
        help="Learn a dog identity from images",
    )

    learn_parser.add_argument(
        "identity",
    )

    learn_parser.add_argument(
        "directory",
    )

    classify_list_parser = subparsers.add_parser(
        "classify-list",
        help="List crop classifications",
    )

    classify_list_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of classifications to show",
    )

    classify_list_parser.add_argument(
        "--identity",
        help="Filter by identity",
    )

    classify_list_parser.add_argument(
        "--unknown",
        action="store_true",
        help="Show only unknown classifications",
    )

    classify_list_parser.add_argument(
        "--confidence-below",
        type=float,
        help="Show classifications below confidence threshold",
    )

    subparsers.add_parser(
        "review",
        help="Show classification statistics",
    )

    export_parser = subparsers.add_parser(
        "export-review",
        help="Export classifications for review",
    )

    export_parser.add_argument(
        "--limit",
        type=int,
    )

    import_review_parser = subparsers.add_parser(
        "import-review",
        help="Import confirmed review images",
    )

    import_review_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show import plan without importing",
    )

    active_review_parser = subparsers.add_parser(
        "active-review",
        help="Export uncertain classifications for review",
    )

    active_review_parser.add_argument(
        "--threshold",
        type=float,
        default=0.80,
    )

    review_apply_parser = subparsers.add_parser(
        "review-apply",
        help="Apply a reviewed classification",
    )

    review_apply_parser.add_argument(
        "classification_id",
        type=int,
    )

    review_apply_parser.add_argument(
        "identity",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show pipeline status",
    )

    status_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show diagnostic information",
    )

    sync_parser = subparsers.add_parser(
        "sync",
        help="Synchronize classifications to Immich albums",
    )

    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying Immich",
    )

    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run complete processing pipeline",
    )

    pipeline_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of items processed per stage",
    )

    pipeline_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pipeline plan without running",
    )

    pipeline_parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess existing assets",
    )

    args = parser.parse_args(argv)

    if args.command == "config-check":
        config_check_command(args)

    elif args.command == "init-db":
        init_db_command(args)

    elif args.command == "test-immich":
        test_immich_command(args)

    elif args.command == "scan":
        scan_command(args)

    elif args.command == "download":
        download_command(args)

    elif args.command == "detect":
        detect_command(args)

    elif args.command == "classify":
        classify_command(args)

    elif args.command == "test-embedding":
        test_embedding_command(args)

    elif args.command == "learn":
        learn_command(args)

    elif args.command == "classify-list":
        classify_list_command(args)

    elif args.command == "review":
        review_command(args)

    elif args.command == "export-review":
        export_review_command(args)

    elif args.command == "import-review":
        import_review_command(args)

    elif args.command == "active-review":
        active_review_command(args)

    elif args.command == "review-apply":
        review_apply_command(args)

    elif args.command == "status":
        status_command(args)

    elif args.command == "sync":
        sync_command(args)

    elif args.command == "pipeline":
        pipeline_command(args)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
