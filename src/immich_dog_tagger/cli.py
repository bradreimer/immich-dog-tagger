"""
Command line interface for Immich Dog Tagger.
"""

import argparse

from .config import load_config


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

    args = parser.parse_args()

    if args.command == "scan":
        print("Scanner not implemented yet.")

    elif args.command == "config-check":
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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
