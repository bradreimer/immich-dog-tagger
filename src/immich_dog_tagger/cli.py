"""
Command line interface for Immich Dog Tagger.
"""

from pathlib import Path
from sqlalchemy.orm import Session
import argparse

from .config import load_config
from .crops import CropWriter
from .database import create_database
from .detection import DetectionService
from .downloader import Downloader
from .immich import ImmichClient
from .learner import Learner
from .openclip_embedder import OpenClipEmbedder
from .scanner import Scanner
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

    elif args.command == "test-yolo":
        config = load_config()

        detector = YOLODetector(
            config.yolo_model,
        )

        detections = detector.detect(
            args.image,
        )

        for detection in detections:
            print(f"{detection.label:12}{detection.confidence:.2f}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
