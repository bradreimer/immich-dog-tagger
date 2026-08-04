# Classification Pipeline

## Overview

The classification pipeline identifies dog identities from detected dog crops.

The database is the source of truth.

## Flow

```plain
Crop image
|
v
OpenCLIP embedding
|
v
IdentityClassifier
|
v
Cosine similarity against EmbeddingExample records
|
v
CropClassification
```

## Components

### OpenClipEmbedder

Creates vector embeddings from crop images.

### EmbeddingExample

Stores known dog examples.

Each example contains:

- identity
- crop path
- embedding vector
- source provenance

### IdentityClassifier

Current implementation:

1. Loads all embedding examples.
2. Calculates cosine similarity.
3. Selects highest scoring example.
4. Returns identity and similarity score.

## Current limitations

- Only the top identity is retained.
- Similarity is used as confidence.
- Alternative candidates are discarded.
- Temporal information is not considered.

## v0.8.0 Direction

Improve classification by:

- retaining ranked candidates
- separating similarity from confidence
- adding temporal context
- improving active learning