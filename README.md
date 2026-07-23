# Immich Dog Tagger

AI-assisted dog detection and identity classification pipeline for [Immich](https://immich.app/).

Immich Dog Tagger scans an Immich photo library, detects dogs, creates crops, generates image embeddings, and classifies individual dogs using a locally trained identity model.

The workflow is designed around human-in-the-loop learning:

1. Detect dogs
2. Classify predictions
3. Review uncertain results
4. Confirm correct identities
5. Feed confirmed examples back into training

The goal is to identify individual dogs such as:

- Hermann
- Fibonacci (Fibs)
- Henri

while keeping all processing local.

---

## Features

Current capabilities:

- Scan an Immich library through the Immich API
- Maintain local processing state in SQLite
- Download and cache assets
- Detect dogs using YOLO
- Generate dog crops
- Generate image embeddings using OpenCLIP
- Classify dogs using embedding similarity
- Track classification confidence
- Track classification provenance:
  - automatic predictions
  - human review corrections
- Review uncertain classifications
- Create new training examples from reviewed results
- Incrementally build a local identity dataset
- Sync identified dogs back into Immich albums

---

## Architecture

The processing pipeline:

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

Processing is split into independent stages:

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
  Validate uncertain predictions

sync
  Update Immich albums
```

---

## Requirements

- Python 3.14+
- `uv`
- SQLite
- Immich instance with API access
- NVIDIA GPU recommended for local AI inference

Tested development environment:

- Ubuntu Linux
- NVIDIA CUDA
- RTX-class GPU

CPU execution is possible but will be significantly slower.

---

## Installation

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

## Configuration

Create your configuration file:

```bash
immich-dog-tagger config-check
```

Configuration includes:

- Immich URL
- Immich API key
- State directory
- Cache directory
- Crop storage location
- YOLO model path

The application separates persistent state from rebuildable cache data.

Example storage layout:

```plain
data/breimer/
├── state/
│ └── state.db
└── cache/
  ├── assets/
  ├── crops/
  └── review/
```

The state directory contains the SQLite database and processing metadata.

The cache directory contains downloaded assets, generated crops, and review artifacts. Cache contents can be deleted and regenerated if required.

All generated data remains local.

---

## Initialize the Database

Create the local SQLite database:

```bash
immich-dog-tagger init-db
```

The database stores:

- discovered assets
- detections
- crops
- classifications
- identities
- embedding examples

---

# First Processing Run

The complete pipeline can be executed with:

```bash
immich-dog-tagger pipeline
```

The pipeline runs:

1. Scan Immich assets
2. Download new images
3. Detect dogs
4. Create crops
5. Classify identities

Example output:

```
Scanning Immich
Scanned 250 assets

Downloading assets
Downloaded 250 assets

Detecting dogs
Detected 87 dogs

Classifying dogs
Classified 87 crops

Pipeline complete
```

---

## Dry Run

Preview pipeline actions without processing:

```bash
immich-dog-tagger pipeline --dry-run
```

---

## Processing Limits

For testing:

```bash
immich-dog-tagger pipeline --limit 25
```

The limit applies independently to each pipeline stage.

---

## Reprocessing

To rebuild existing detections or classifications:

```bash
immich-dog-tagger pipeline --force
```

Use this when:

- changing detection models
- changing crop settings
- rebuilding embeddings
- correcting processing state

---

# Review Workflow

Classification improves through review.

View uncertain classifications:

```bash
immich-dog-tagger active-review
```

Review items are ranked by confidence so the least certain predictions appear first.

Example:

```
ID   Identity    Confidence   Image
42   Unknown     0.42         crop_0042.jpg
43   Hermann     0.67         crop_0043.jpg
44   Fibs        0.73         crop_0044.jpg
```

Apply a correction:

```bash
immich-dog-tagger review-apply 42 Hermann
```

A reviewed classification:

- changes the predicted identity
- records the correction source
- creates a new embedding example

These examples improve future classification accuracy.

---

# Learning

Training examples are built incrementally.

A confirmed review creates an identity example:

```
Crop image
   |
   v
Embedding generation
   |
   v
Identity example
```

Future classifications compare new crops against these examples.

This avoids retraining a large model and allows the system to improve gradually as more photos are reviewed.

---

# Syncing Results

After classifications are confirmed:

```bash
immich-dog-tagger sync
```

The sync stage updates Immich albums:

```
Dog - Hermann
Dog - Fibonacci
Dog - Henri
```

---

# Development

Install development dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Run formatting and validation:

```bash
uv run ruff check --fix .
uv run ruff format
uv run pytest -q
```

---

# Project Status

Current status:

✅ Immich asset discovery  
✅ Asset downloading and caching  
✅ YOLO dog detection  
✅ Crop generation  
✅ OpenCLIP embeddings  
✅ Identity classification  
✅ Confidence-based review workflow  
✅ Human feedback learning loop  
✅ Immich album synchronization  

Future improvements:

- Automatic background processing
- Better review UI
- More advanced identity models
- Improved duplicate detection
- Scheduled Immich synchronization

---

# Design Goals

The project intentionally avoids:

- cloud AI services
- uploading personal photos externally
- retraining large neural networks
- modifying Immich internals

The goal is a small local assistant that gradually learns the identities of the dogs in a personal photo library.