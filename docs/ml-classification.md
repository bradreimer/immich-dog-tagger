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

1. Loads all embedding examples (per species).
2. Calculates cosine similarity between the query embedding and each example.
3. Weights each example's similarity by how closely its own capture date (`EmbeddingExample.
   captured_at`) aligns with the photo being classified (`captured_at` passed into `classify()`) --
   see "Temporal-recency weighting" below.
4. Per identity, selects the example maximizing `similarity * temporal_weight` and ranks
   candidates by that combined score.
5. Returns the winning identity along with its **raw, unweighted** cosine similarity as
   confidence -- the temporal signal decides which identity wins, never what confidence number is
   reported (see v1.0.0.md section 8 and ADR-003).

### Temporal-recency weighting (v1.5, ADR-003)

Each candidate example gets a `temporal_weight` in `[TEMPORAL_FLOOR, 1.0]` (`scoring.py`),
computed from the gap between the query photo's `captured_at` and the example's own
`captured_at`:

- `1.0` when the two dates coincide, or when either date is missing (fail open -- absence of
  date evidence is never a penalty).
- Gaussian decay toward `TEMPORAL_FLOOR` (default `0.15`) as the gap grows, with
  `TEMPORAL_SIGMA_DAYS` (default `365`, i.e. about a year) as the characteristic scale.
- Never reaches zero -- a lone identity with only old examples and no closer-in-time competing
  identity still classifies correctly, since its raw similarity is what gets reported regardless
  of its own temporal_weight.

Weighting is anchored to the query photo's own capture date, not wall-clock "now" -- classifying
an old photo still correctly favors examples from that same era, which is what lets an identity
whose pet has since passed away keep classifying correctly against its own historical photos,
while a new, visually similar identity naturally wins recent photos instead. See
[docs/specs/v1.5-automatic-temporal-classification.md](specs/v1.5-automatic-temporal-classification.md)
and [ADR-003](adr/ADR-003-automatic-temporal-recency-classification.md) for the full rationale.

This replaced DT-1114's owner-configured `Identity.active_from`/`active_until` hard-boundary
flag, which required manual upkeep per identity.

## Current limitations

- Only the top identity per candidate list is retained per identity (one winning example each).
- Alternative candidates beyond the configured limit are discarded.
- The temporal decay curve's scale/floor are fixed constants, not owner-tunable.