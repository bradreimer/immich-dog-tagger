# Immich Dog Tagger

AI-assisted dog detection and identity classification pipeline for [Immich](https://immich.app/).

![immich-dog-tagger project banner](banner.png)

Immich Dog Tagger scans an Immich photo library, detects dogs, creates crops, generates image embeddings, and classifies individual dogs using a locally learned identity model.

The system is designed around human-in-the-loop learning:

1. Detect dogs
2. Generate identity predictions
3. Review uncertain results
4. Correct mistakes
5. Learn from confirmed examples
6. Improve future classifications

The goal is to identify individual dogs such as:

- Hermann
- Fibonacci (Fibs)
- Henri

while keeping all processing local.

## Quick Start

```bash
uv sync

immich-dog-tagger scan
immich-dog-tagger download
immich-dog-tagger detect
immich-dog-tagger classify

uv run uvicorn immich_dog_tagger.api.app:app --reload
```

Open

```
http://localhost:5173
```

Review images.

Run

```bash
immich-dog-tagger sync
```

to publish results back to Immich.

---

# Project Status

Current release:

```
v0.5.0
```

v0.5.0 completes the active learning review workflow. Human corrections are now immediately incorporated into the local identity model, allowing future classifications to improve over time.


Completed:

- FastAPI service layer
- Review queue API
- Prioritized review workflow
- Browser-based classification review
- Keyboard-driven corrections
- Explicit prediction and suggestion models
- Matched example visualization
- Human correction workflow integration
- Immediate learning from corrections
- Review audit history
- Review skip workflow
- Optimistic browser review queue
- Review statistics
- Pipeline health metrics
- Suggested example visualization
- Review filtering
- Browser error handling

---

# Architecture

The central design principle is:

> `state.db` is the source of truth.

Immich is treated as a photo source and presentation target. The local database owns processing state, classifications, review history, and learned examples.

Current architecture:

```
                CLI
                 |
                 v
          Application Services
                 |
                 v
              state.db
                 |
    +------------+------------+
    |                         |
    v                         v

ML Pipeline             Immich Sync


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
```

The CLI remains the operational interface for pipeline execution, maintenance, and automation.

The Web API provides the human interaction layer for review and correction workflows.

---

# Features

## Machine Learning Pipeline

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
- Explain classifications using matched examples

Supported identities include:

- Hermann
- Fibonacci (Fibs)
- Henri

---

## Human Review Workflow

![Review UI](docs/images/review-ui.png)

The review workflow allows the system to improve through human feedback.

Features:

- Prioritized review queue
- Unknown and low-confidence prioritization
- Browser-based review interface
- Keyboard shortcuts for rapid correction:

```
f → Fibonacci
h → Hermann
n → Henri
u → Unknown
```

Each review item can display:

- Current prediction
- Similarity score
- Supporting example when available
- Correction actions

Corrections:

- Update the classification
- Record human provenance
- Create future training examples

---

## Web API

The Web API exposes existing application services through FastAPI.

Current endpoints include:

```plain
GET  /review
GET  /review/stats
POST /classifications/{id}/correct
POST /review/{id}/skip
GET  /crops/{id}
GET  /embedding-examples/{id}/image
GET  /health
```

The API sits above the application layer rather than replacing the CLI or pipeline.

---

# Running Locally

The review API is served by FastAPI via Uvicorn, and the browser UI is served by Vite.

## Backend API

From the repository root, install the Python dependencies and start the API:

```bash
uv sync
uv run uvicorn immich_dog_tagger.api.app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000 and the interactive docs are at http://localhost:8000/docs.

## Web UI

In a second terminal, install the frontend dependencies and start the Vite dev server:

```bash
cd ui
npm install
npm run dev
```

The UI will be available at http://localhost:5173. The Vite dev server proxies requests under /api to the backend on port 8000.

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
Generate identity predictions

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

```

The cache contains rebuildable artifacts.

The database contains knowledge.

---

# Learning System

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

````

As more photos are reviewed, the local identity dataset grows.

The current system uses embedding similarity against learned examples.

---

# Immich Synchronization

After classification:

```bash
immich-dog-tagger sync
````

The sync service projects classifications into Immich albums:

```
Dog - Hermann
Dog - Fibonacci
Dog - Henri
```

Immich remains the presentation layer.

The local database remains authoritative.

---

# Requirements

* Python 3.14+
* `uv`
* SQLite
* Immich instance with API access
* NVIDIA GPU recommended for local AI inference

Tested development environment:

* Ubuntu Linux
* NVIDIA CUDA
* RTX-class GPU

CPU execution is possible but significantly slower.

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
cd immich-dog-tagger
```

Install dependencies:

```bash
uv sync
```

---

# Configuration

Validate configuration:

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

The review workflow is how the system improves.

Start with the browser review interface or CLI tools:

```bash
immich-dog-tagger review
```

A correction:

* updates the classification
* records human provenance
* creates a learning example

immediately updates the local embedding database so future classifications can benefit without requiring an offline retraining step.

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

UI validation:

```bash
cd ui
npm run build
npm run lint
```

Current validation:

```
Python tests: 112 passed
UI build: passing
UI lint: passing
```

---

# Roadmap

## Next: v0.6.0

The next milestone focuses on improving classification quality.

Planned areas include:

- richer nearest-neighbor ranking
- temporal context during classification
- improved training example management
- browser UX improvements
- Immich synchronization enhancements

---

# Design Goals

The project intentionally avoids:

* cloud AI services
* uploading personal photos externally
* modifying Immich internals
* retraining large neural networks

The goal is a small local assistant that gradually learns the identities of the dogs in a personal photo library.

> **The database is the brain.  
> The ML pipeline is the nose.  
> Immich is the gallery.  
> The review UI is the trainer.**
