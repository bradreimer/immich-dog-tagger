"""
Command line interface for Immich Dog Tagger.
"""

import argparse
import logging

from sqlalchemy.orm import Session

from .config import load_config
from .database import create_database
from .downloader import Downloader
from .enums import ClassificationMode, PipelineOperation
from .immich import ImmichClient
from .policy import DEFAULT_POLICY
from .review_export import ReviewExporter
from .review_import import ReviewImporter
from .runtime import get_embedder
from .services.albums import AlbumService
from .services.backup import BackupError, BackupService
from .services.correction import ClassificationCorrectionService
from .services.derived_data import DerivedDataService
from .services.job_execution import create_pipeline_job_runner
from .services.jobs import PipelineJobService
from .services.learner import Learner
from .services.pet_occurrences import PetOccurrenceService
from .services.review_query import ReviewQueryService
from .services.status import PipelinePlan, StatusService
from .services.sync import SyncService
from .services.tags import TagService


def run_operation_job(
    session: Session,
    config,
    operation: PipelineOperation,
    *,
    options: dict | None = None,
) -> dict:
    operation_options = {}

    if options is not None:
        operation_options[operation] = options

    runner = create_pipeline_job_runner(
        session,
        config,
        operation_options=operation_options,
    )

    service = PipelineJobService(
        session,
        repository=runner.repository,
    )

    job = service.create_job(operation=operation)

    try:
        result = runner.run_job(job.id)
    except (RuntimeError, ValueError) as exc:
        print(f"Job {job.id} failed: {exc}")
        raise SystemExit(1) from exc

    return result if isinstance(result, dict) else {}


def backup_command(args) -> None:
    config = load_config()
    svc = BackupService(config.state_dir)
    try:
        result = svc.create_backup()
        print(f"Backup created: {result.path}")
        print(f"Size: {result.size_bytes} bytes")
        print(f"Created at: {result.created_at.isoformat()}")
    except BackupError as exc:
        print(f"Backup failed: {exc}")
        raise SystemExit(1) from exc


def validate_backup_command(args) -> None:
    from pathlib import Path

    config = load_config()
    svc = BackupService(config.state_dir)
    path = Path(args.path)
    try:
        svc.validate_backup(path)
        print(f"Backup is valid: {path}")
    except BackupError as exc:
        print(f"Backup invalid: {exc}")
        raise SystemExit(1) from exc


def restore_command(args) -> None:
    from pathlib import Path

    config = load_config()
    svc = BackupService(config.state_dir)
    path = Path(args.path)
    try:
        rollback = svc.restore_backup(path)
        print(f"Restored from: {path}")
        print(f"Rollback copy: {rollback}")
    except BackupError as exc:
        print(f"Restore failed: {exc}")
        raise SystemExit(1) from exc


def check_derived_data_command(args) -> None:
    config = load_config()
    engine = create_database(config.state_dir)
    with Session(engine) as session:
        svc = DerivedDataService(session, config.cache_dir)

        if getattr(args, "repair", False):
            summary = svc.repair()
            print(f"Repaired {summary.total_repaired} asset(s):")
            print(f"  Routed back to download: {summary.downloads_repaired}")
            print(f"  Routed back to detect:   {summary.crops_repaired}")
            print()
            report = svc.check()
        else:
            report = svc.check()

    if report.healthy:
        print("Derived data: all referenced artifacts present")
    else:
        print(f"Derived data: {report.total_missing} missing artifact(s)")
        print(f"  Missing downloads:          {len(report.missing_downloads)}")
        print(f"  Missing crops:              {len(report.missing_crops)}")
        print(f"  Missing embedding sources:  {len(report.missing_embedding_sources)}")
        print()
        for line in DerivedDataService.rebuild_guidance(report):
            print(line)
        raise SystemExit(1)


def backfill_occurrences_command(args) -> None:
    config = load_config()

    engine = create_database(config.state_dir)

    with Session(engine) as session:
        processed = PetOccurrenceService(session).sync_all()

    print(f"Processed {processed} classification(s)")


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

    engine = create_database(config.state_dir)

    with Session(engine) as session:
        result = run_operation_job(
            session,
            config,
            PipelineOperation.SCAN,
        )

    print(f"New assets: {result.get('scanned', 0)}")


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

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        result = run_operation_job(
            session,
            config,
            PipelineOperation.DETECT,
            options={
                "limit": args.limit,
            },
        )

        print(f"Processed: {result.get('processed', 0)}")
        print(f"Detections: {result.get('detections', 0)}")
        print(f"Dogs: {result.get('dogs', 0)}")
        print(f"Cats: {result.get('cats', 0)}")
        print(f"Failed: {result.get('failed', 0)}")


def classify_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        mode = ClassificationMode.ALL if args.all else ClassificationMode.PENDING

        result = run_operation_job(
            session,
            config,
            PipelineOperation.CLASSIFY,
            options={
                "limit": args.limit,
                "threshold": args.threshold,
                "mode": mode,
            },
        )

    print(f"Classified: {result.get('classified', 0)}")

    for identity, count in result.get("identities", {}).items():
        print(f"{identity}: {count}")


def learn_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        result = run_operation_job(
            session,
            config,
            PipelineOperation.LEARN,
            options={
                "identity": args.identity,
                "directory": args.directory,
                "species": args.species,
            },
        )

    print(f"Learned examples: {result.get('imported', 0)}")


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
            f"{item.prediction.identity or 'Unknown'!s:<12}"
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
    print()
    print("Learning")
    print("--------")
    print("Examples by source:")
    for source, count in summary.examples_by_source.items():
        print(f"  {source}: {count}")
    print("Review actions by type:")
    for action, count in summary.review_actions_by_type.items():
        print(f"  {action}: {count}")

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

    if args.dry_run:
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
                tags=TagService(client),
            )

            summary = service.sync(
                dry_run=True,
            )

        print("Would sync:")

        for item in summary.identities:
            print(f"{item.identity}: {item.assets}")

        skipped = (
            summary.skipped_low_confidence
            + summary.skipped_unknown
            + summary.skipped_missing_asset
        )

        if skipped:
            print()
            print(f"Skipped {skipped} classification(s):")
            print(f"  {summary.skipped_low_confidence} below confidence threshold")
            print(f"  {summary.skipped_unknown} unidentified")
            print(f"  {summary.skipped_missing_asset} missing asset data")

        return

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
        result = run_operation_job(
            session,
            config,
            PipelineOperation.SYNC,
        )

    for item in result.get("items", []):
        print(f"{item['identity']}: {item['assets']}")


def pipeline_command(args) -> None:
    config = load_config()

    engine = create_database(
        config.state_dir,
    )

    with Session(engine) as session:
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

        result = run_operation_job(
            session,
            config,
            PipelineOperation.FULL_PIPELINE,
            options={
                "limit": args.limit,
                "force": args.force,
                "progress_callback": lambda message: print(message, flush=True),
            },
        )

    print("Pipeline complete")
    print()

    print("Summary")
    print("-------")
    print(f"Assets scanned:     {result.get('scanned', 0)}")
    print(f"Downloaded:         {result.get('downloaded', 0)}")
    print(f"Dogs detected:      {result.get('detected', 0)}")
    print(f"Classified:         {result.get('classified', 0)}")


def main(argv: list[str] | None = None) -> None:
    # Without a root handler, logger.info(...) calls throughout the app
    # (e.g. pipeline batch progress) are silently dropped -- see
    # api/app.py's identical setup for the uvicorn-served process.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

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
        default=DEFAULT_POLICY.confident_threshold,
        help="Minimum confidence required for identity assignment",
    )

    classify_parser.add_argument(
        "--all",
        action="store_true",
        help="Reclassify already classified crops",
    )

    learn_parser = subparsers.add_parser(
        "learn",
        help="Add reference examples for a dog or cat identity from images",
    )

    learn_parser.add_argument(
        "identity",
    )

    learn_parser.add_argument(
        "directory",
    )

    learn_parser.add_argument(
        "--species",
        choices=["dog", "cat"],
        default="dog",
        help="Species of the identity being taught (default: dog)",
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
        default=DEFAULT_POLICY.confident_threshold,
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

    subparsers.add_parser(
        "backup",
        help="Create a backup of state.db",
    )

    validate_backup_parser = subparsers.add_parser(
        "validate-backup",
        help="Validate a state.db backup file",
    )
    validate_backup_parser.add_argument("path", help="Path to the backup file")

    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore state.db from a backup (creates rollback copy first)",
    )
    restore_parser.add_argument("path", help="Path to the backup file to restore")

    check_derived_data_parser = subparsers.add_parser(
        "check-derived-data",
        help="Check for missing derived artifacts (crops, embeddings, downloads)",
    )
    check_derived_data_parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "Route assets with a missing cached original or crop file back "
            "through download/detect instead of only reporting them"
        ),
    )

    subparsers.add_parser(
        "backfill-occurrences",
        help="Rebuild pet occurrence facts from current classification state (issue #94)",
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

    elif args.command == "backup":
        backup_command(args)

    elif args.command == "validate-backup":
        validate_backup_command(args)

    elif args.command == "restore":
        restore_command(args)

    elif args.command == "check-derived-data":
        check_derived_data_command(args)

    elif args.command == "backfill-occurrences":
        backfill_occurrences_command(args)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
