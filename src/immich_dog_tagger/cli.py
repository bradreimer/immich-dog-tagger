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
from .immich import ImmichClient
from .openclip_embedder import OpenClipEmbedder
from .review_export import ReviewExporter
from .review_import import ReviewImporter
from .scanner import Scanner
from .services.albums import AlbumService
from .services.classification import ClassificationService
from .services.detection import DetectionService
from .services.learner import Learner
from .services.pipeline import PipelineService
from .services.review import ReviewService
from .services.status import StatusService
from .services.sync import SyncService
from .yolo_detector import YOLODetector


def main() -> None:
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
        "review-stats",
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

    subparsers.add_parser(
        "status",
        help="Show pipeline status",
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

    subparsers.add_parser(
        "pipeline",
        help="Run complete processing pipeline",
    )

    args = parser.parse_args()

    if args.command == "config-check":
        config = load_config()

        print("Immich:")
        print(f"  URL: {config.immich_url}")

        if config.immich_api_key:
            print("  API key: configured")
        else:
            print("  API key: missing")

        print()
        print("Storage:")
        print(f"  Data directory: {config.data_dir}")

    elif args.command == "init-db":
        config = load_config()

        create_database(config.data_dir)

        print(f"Database initialized: {config.data_dir / 'state.db'}")

    elif args.command == "test-immich":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        assets = client.list_assets()

        print(f"Found {len(assets)} assets")

    elif args.command == "scan":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        engine = create_database(config.data_dir)

        with Session(engine) as session:
            scanner = Scanner(
                client,
                session,
            )

            count = scanner.scan()

        print(f"New assets: {count}")

    elif args.command == "download":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        engine = create_database(config.data_dir)

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

    elif args.command == "detect":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        detector = YOLODetector(
            config.yolo_model,
        )

        engine = create_database(
            config.data_dir,
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

    elif args.command == "classify":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        embedder = OpenClipEmbedder()

        with Session(engine) as session:
            classifier = IdentityClassifier(session)

            service = ClassificationService(
                session,
                embedder,
                classifier,
            )

            summary = service.classify_pending(
                limit=args.limit,
                threshold=args.threshold,
            )

        print(f"Classified: {summary.classified}")

        for identity, count in summary.identities.items():
            print(f"{identity}: {count}")

    elif args.command == "test-embedding":
        embedder = OpenClipEmbedder()

        embedding = embedder.embed(Path(args.image))

        print(f"Dimensions: {embedding.shape[0]}")
        print(f"First values: {embedding[:5]}")

    elif args.command == "learn":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        embedder = OpenClipEmbedder()

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

    elif args.command == "classify-list":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        with Session(engine) as session:
            service = ReviewService(session)

            classifications = service.classifications(
                limit=args.limit,
                identity=args.identity,
                unknown=args.unknown,
            )

        print(f"{'ID':<8}{'Identity':<12}{'Confidence':<14}{'File':<40}Match")

        for item in classifications:
            print(
                f"{item.classification_id:<8}"
                f"{str(item.identity):<12}"
                f"{item.confidence:<14.4f}"
                f"{item.filename:<40}"
                f"{item.matched_example_path or ''}"
            )

    elif args.command == "review-stats":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        with Session(engine) as session:
            service = ReviewService(session)
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

    elif args.command == "export-review":
        config = load_config()

        engine = create_database(config.data_dir)

        with Session(engine) as session:
            review = ReviewService(session)

            items = review.classifications(
                limit=args.limit,
            )

        exporter = ReviewExporter()

        count = exporter.export(
            items,
            config.data_dir / "review",
        )

        print(f"Exported: {count}")

    elif args.command == "import-review":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        embedder = OpenClipEmbedder()

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
                    config.data_dir / "review" / "confirmed",
                )

                print("Would import:")

                for identity, count in plan.identities.items():
                    print(f"{identity}: {count}")

                print()
                print(f"Total: {plan.total}")

            else:
                summary = importer.import_confirmed(
                    config.data_dir / "review" / "confirmed",
                )

                print(f"Imported: {summary.imported}")

                for identity, count in summary.identities.items():
                    print(f"{identity}: {count}")

    elif args.command == "active-review":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        with Session(engine) as session:
            review = ReviewService(session)

            items = review.active_review(
                threshold=args.threshold,
            )

        exporter = ReviewExporter()

        count = exporter.export(
            items,
            config.data_dir / "review" / "active",
        )

        print(f"Exported: {count}")

    elif args.command == "review-apply":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        embedder = OpenClipEmbedder()

        with Session(engine) as session:
            learner = Learner(
                embedder,
                session,
            )

            review = ReviewService(
                session,
                learner,
            )

            review.apply_review(
                args.classification_id,
                args.identity,
            )

            session.commit()

        print(f"Applied review: {args.classification_id} -> {args.identity}")

    elif args.command == "status":
        config = load_config()

        engine = create_database(
            config.data_dir,
        )

        with Session(engine) as session:
            service = StatusService(session)
            summary = service.summary()

        print(f"Assets:             {summary.assets}")
        print(f"Detections:         {summary.detections}")
        print(f"Crops:              {summary.crops}")
        print(f"Classifications:    {summary.classifications}")
        print(f"Identities:         {summary.identities}")
        print(f"Embedding examples: {summary.examples}")

    elif args.command == "sync":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        engine = create_database(
            config.data_dir,
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

        for identity, count in summary.items():
            print(f"{identity}: {count}")

    elif args.command == "pipeline":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        engine = create_database(
            config.data_dir,
        )

        detector = YOLODetector(
            config.yolo_model,
        )

        embedder = OpenClipEmbedder()

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

            summary = pipeline.run(
                progress=lambda message: print(f"{message}...", flush=True),
            )

        print("Pipeline complete")
        print()

        print("Summary")
        print("-------")
        print(f"Assets scanned:     {summary.scanned}")
        print(f"Downloaded:         {summary.downloaded}")
        print(f"Dogs detected:      {summary.detected}")
        print(f"Classified:         {summary.classified}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
