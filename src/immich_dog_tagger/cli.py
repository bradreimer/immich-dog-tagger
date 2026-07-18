"""
Command line interface for Immich Dog Tagger.
"""

import argparse
from sqlalchemy.orm import Session 

from .config import load_config
from .database import create_database
from .immich import ImmichClient
from .scanner import Scanner


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

        create_database(
            config.data_dir
        )

        print(
            f"Database initialized: {config.data_dir / 'state.db'}"
        )

    elif args.command == "test-immich":
        config = load_config()

        client = ImmichClient(
            config.immich_url,
            config.immich_api_key,
        )

        assets = client.list_assets()

        print(
            f"Found {len(assets)} assets"
        )
        
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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
