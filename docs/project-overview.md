# Immich Dog Tagger Project Overview

## Project Name
Immich Dog Tagger

## Purpose
Immich Dog Tagger identifies individual dogs in an Immich photo library and builds a searchable organization workflow around those identities.

The initial motivation is recognizing Fibs, Hermann, and Henri across a large personal photo collection.

## User Problem
Photo libraries contain thousands of images where the same dogs appear across years, lighting conditions, cameras, and imperfect metadata. Manual tagging is slow and inconsistent.

## Long-Term Vision
Create a self-improving local-first dog recognition system:
- detect dogs in photos
- classify identities
- collect human corrections
- learn from confirmed examples
- synchronize results back to Immich

## Current Maturity
The project has moved beyond experimentation into an early product phase:
- ML detection pipeline exists
- state database exists
- review API exists
- browser review workflow exists
- active learning loop exists

## Design Principles
- state.db is the source of truth
- Immich is a presentation/export target
- local-first processing
- human corrections improve future classification
- small commits with tests after changes
- explicit provenance for learned data

## Technology Stack
- Python
- SQLAlchemy
- FastAPI
- React + Vite + TypeScript
- YOLO object detection
- OpenCLIP embeddings
- pytest
- ruff
- uv

## Architecture Decisions
The project separates:
1. Asset ingestion
2. Detection
3. Cropping
4. Classification
5. Human review
6. Learning
7. External synchronization

This prevents Immich API state from becoming the authoritative model.

## Constraints
- Must run locally
- Must handle tens of thousands of photos
- Must preserve explainability of classifications
- Must support incremental improvement
