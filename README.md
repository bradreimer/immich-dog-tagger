# Immich Dog Tagger

AI-assisted dog detection and identity classification pipeline for [Immich](https://immich.app/).

Immich Dog Tagger scans a photo library, detects dogs, creates crops, generates image embeddings, and classifies individual dogs using a locally trained identity model.

The current workflow is designed around human-in-the-loop learning:

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
- Export predictions for human review
- Import confirmed examples for continued learning
- Incrementally build a local identity dataset

---

## Architecture

The processing pipeline:
