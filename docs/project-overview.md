# Project overview

## What it does

Immich Dog Tagger finds individual dogs and cats in an Immich photo library and lets you build a
searchable, correctly tagged collection around their identities. The original motivation:
recognizing three specific dogs — Fibs, Hermann, and Henri — across a personal photo library too
large to tag by hand.

## Why it matters

A photo library accumulates thousands of images of the same pets across years, cameras, and
lighting conditions. Manually tagging "which dog is this" doesn't scale, and Immich itself has no
concept of pet identity. This project closes that gap without sending any photo data off the
machine it runs on.

## How it works

1. Detect dogs and cats in photos (YOLO)
2. Classify their identity by embedding similarity against reviewed examples
3. Show uncertain predictions to a human for review
4. Turn each correction into a new reference example
5. Sync confirmed identities back to Immich as albums

## Current state

Past the experimentation stage: the detection pipeline, the state database, the review API, the
browser review workflow, and the active-learning loop are all built and in use. See
[docs/status.md](status.md) for what's shipped and what's next.

## Design principles

- `state.db` is the source of truth; Immich is a photo source and sync target only
- Everything runs locally — no photo or image data goes to an external service
- A human correction is ground truth; a classifier prediction is derived and reproducible
- Small commits with tests
- Explicit provenance for every learned example (automatic vs. human-confirmed)

## Technology stack

Python, SQLAlchemy, FastAPI, React + Vite + TypeScript, YOLO, OpenCLIP, pytest, ruff, uv.

## Architecture

The pipeline separates ingestion, detection, cropping, classification, human review, learning,
and Immich sync into distinct stages, so Immich's API never becomes the system's memory — that
stays in `state.db`. See [ADR-001](adr/ADR-001-state-database-source-of-truth.md).

## Constraints

- Must run entirely on local hardware
- Must handle photo libraries in the tens of thousands
- Every classification must be explainable (which example it matched, how similar, when)
- Must improve incrementally from review, without a full retraining step
