"""
Command line interface for Immich Dog Tagger.
"""

import argparse


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

    args = parser.parse_args()

    if args.command == "scan":
        print("Scanner not implemented yet.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
