# Immich Dog Tagger

AI-assisted dog detection and identity classification pipeline for [Immich](https://immich.app/).

![immich-dog-tagger project banner](banner.png)

Immich Dog Tagger scans an Immich photo library, detects dogs, creates crops, generates image embeddings, and classifies individual dogs using a locally trained identity model.

The system is designed around human-in-the-loop learning:

1. Detect dogs
2. Classify predictions
3. Review uncertain results
4. Correct mistakes
5. Learn from confirmed examples
6. Improve future classifications

The goal is to identify individual dogs such as:

- Hermann
- Fibonacci (Fibs)
- Henri

while keeping all processing local.

---

# Project Status

Current release:

```

v0.2.0

```

The v0.2.0 milestone completes the core machine learning pipeline, review workflow, learning loop, and Immich synchronization.

The next milestone:

```

v0.3.0 Web API

```

introduces a FastAPI service layer and browser-based workflows built on top of the existing architecture.

---

# Architecture

The central design principle is:

> `state.db` is the source of truth.

Immich is treated as a photo source and presentation target. The local database owns processing state, classifications, review history, and learned examples.

Current architecture:

```

```
         CLI
          |
          v
    Application Services
          |
          v
       state.db

          |
  +-------+-------+
  |               |
  v               v
```

ML Pipeline     Immich Sync

```

Future web architecture:

```

```
         Browser
            |
            v
        FastAPI API
            |
            v
    Application Services
            |
            v
         state.db

            |
    +-------+-------+
    |               |
    v               v

 ML Pipeline    Immich Sync
```

```

The CLI remains an operator and maintenance interface. The Web API becomes the primary human interaction layer.

---

# Features

## Completed in v0.2.0

- Scan an Immich library through the Immich API
- Maintain persistent local processing state
- Download and cache assets
- Detect dogs using YOLO
- Generate dog crops
- Generate embeddings using OpenCLIP
- Classify dogs using embedding similarity
- Track classification confidence
- Track classification provenance:
  - automatic predictions
  - human corrections
- Review uncertain classifications
- Correct classifications
- Generate training examples from reviewed results
- Incrementally build a local identity dataset
- Explain classifications using matched examples
- Synchronize identified dogs back into Immich albums

Supported identities include:

- Hermann
- Fibonacci (Fibs)
- Henri

---

# Processing Pipeline

```

Immich
|
v
Scanner
|
v
Downloader
|
v
YOLO Dog Detection
|
v
Crop Generation
|
v
OpenCLIP Embeddings
|
v
Identity Classification
|
v
Human Review
|
v
Learning Examples
|
v
Improved Classification

```

Processing stages:

```

scan
Discover assets from Immich

download
Cache local copies

detect
Locate dogs and create crops

classify
Identify individual dogs

review
Inspect and correct predictions

learn
Add confirmed examples

sync
Update Immich albums

```

---

# Database

The SQLite database is the system of record.

It stores:

- discovered assets
- detections
- crops
- classifications
- identities
- embedding examples
- review corrections
- provenance metadata

Example:

```

data/breimer/

├── state/
│   └── state.db
│
└── cache/
├── assets/
├── crops/
└── review/

````

The cache contains rebuildable artifacts.

The database contains knowledge.

---

# Requirements

- Python 3.14+
- `uv`
- SQLite
- Immich instance with API access
- NVIDIA GPU recommended for local AI inference

Tested development environment:

- Ubuntu Linux
- NVIDIA CUDA
- RTX-class GPU

CPU execution is possible but significantly slower.

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
cd immich-dog-tagger
````

Install dependencies:

```bash
uv sync
```

---

# Configuration

Create your configuration:

```bash
immich-dog-tagger config-check
```

Configuration includes:

* Immich URL
* Immich API key
* State directory
* Cache directory
* Crop storage location
* YOLO model path

---

# Processing

Run the complete pipeline:

```bash
immich-dog-tagger pipeline
```

Preview processing:

```bash
immich-dog-tagger pipeline --dry-run
```

Limit processing:

```bash
immich-dog-tagger pipeline --limit 25
```

---

# Review Workflow

Review is how the system improves.

View items requiring attention:

```bash
immich-dog-tagger review
```

Corrections become training data.

A correction:

* updates the classification
* records human provenance
* creates a new embedding example

Future predictions use these examples.

---

# Learning

The learning system uses incremental examples rather than retraining a large neural network.

```
Confirmed Crop
      |
      v
Embedding
      |
      v
Identity Example
      |
      v
Future Classification
```

The model improves gradually as more photos are reviewed.

---

# Immich Synchronization

After classification:

```bash
immich-dog-tagger sync
```

The sync service projects classifications into Immich albums:

```
Dog - Hermann
Dog - Fibonacci
Dog - Henri
```

Immich remains a presentation layer.

---

# v0.3.0 Web API Roadmap

The next milestone exposes the existing system through FastAPI.

Planned:

* REST API foundation
* Browser-based review workflow
* Review queue endpoint
* Dog browsing endpoint
* Classification correction endpoint
* Improved human interaction workflows

The API will sit above the existing services rather than replacing them.

---

# Development

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Run validation:

```bash
uv run ruff check --fix .
uv run ruff format
uv run pytest -q
```

Current validation:

```
92 passed
```

---

# Design Goals

The project intentionally avoids:

* cloud AI services
* uploading personal photos externally
* modifying Immich internals
* retraining large neural networks

The goal is a small local assistant that gradually learns the identities of the dogs in a personal photo library.

The database is the brain.
Immich is the gallery.
The Web API is the leash.
