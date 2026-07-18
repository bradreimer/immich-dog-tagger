# Immich Dog Tagger

AI-assisted dog detection and tagging pipeline for Immich.

## Development

This project uses `uv` for Python environment and dependency management.

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Run the application:

```bash
uv run immich-dog-tagger --help
```

## Architecture

The project will eventually provide:

- Immich asset scanning
- Incremental processing
- Dog detection
- Breed classification
- Immich metadata updates

Processing state is stored locally so repeated scans only process new or changed assets.
