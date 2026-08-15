# Classification pipeline

Identifies which dog or cat appears in a detected crop, using nearest-neighbor similarity against
your reviewed examples. `state.db` is the source of truth for those examples; the model weights
never change.

## Flow

```
Crop image
  → OpenCLIP embedding
  → IdentityClassifier
  → cosine similarity against each identity's EmbeddingExample records
  → ranked candidates
  → confident / needs-review / unknown decision (ClassifierPolicy)
  → CropClassification
```

## Components

**`OpenClipEmbedder`** turns a crop image into a vector embedding.

**`EmbeddingExample`** is one known example of an identity: an embedding vector, the crop it came
from, and provenance (automatic prediction vs. human correction).

**`IdentityClassifier`** (`src/immich_dog_tagger/classifier.py`) does the matching:

1. Loads active examples for the crop's species (dog crops are never compared against cat
   examples, and vice versa).
2. Scores cosine similarity between the crop's embedding and every example.
3. Keeps each identity's single best-matching example, then ranks identities by that score.
4. Returns the top candidates (3 by default), not just the winner.
5. Flags — never silently excludes — a candidate whose identity has an owner-set active date
   range that the crop's capture date falls outside (`date_conflict`).

**`ClassifierPolicy`** (`src/immich_dog_tagger/policy.py`) is the single place that owns the
confidence threshold (0.80 by default), candidate-list size, and the confident/needs-review/unknown
decision. The pipeline, `Reclassify`, and the review queue all read from it, so the meaning of
"confident" is the same everywhere it appears. The policy version is stored alongside every
`CropClassification`, so a prediction can always be traced back to the configuration that
produced it.

## What this doesn't do

- **No calibrated confidence.** Similarity is a raw cosine score against your own examples, not a
  validated accuracy or probability estimate.
- **No temporal weighting.** A capture date can flag a candidate as out-of-range, but it never
  boosts or discounts a similarity score.
- **No retraining.** "Learning" means adding reference examples, not updating model weights.

See [docs/specs/v1.0.0.md](specs/v1.0.0.md) section 8 for the full list of things classification
deliberately doesn't claim.
