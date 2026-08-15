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
3. Weights each example's similarity by how closely its own capture date aligns with the crop
   being classified (`temporal_weight`, a Gaussian decay with a ~1 year scale, fails open when a
   date is missing on either side) — see [ADR-003](adr/ADR-003-automatic-temporal-recency-classification.md).
4. Keeps each identity's best-matching example by that *weighted* score, then ranks identities the
   same way — but reports the winning match's raw, unweighted similarity as confidence, so recency
   decides which identity wins without inflating or discounting the number shown.
5. Returns the top candidates (3 by default), not just the winner.

**`ClassifierPolicy`** (`src/immich_dog_tagger/policy.py`) is the single place that owns the
confidence threshold (0.80 by default), candidate-list size, and the confident/needs-review/unknown
decision. The pipeline, `Reclassify`, and the review queue all read from it, so the meaning of
"confident" is the same everywhere it appears. The policy version is stored alongside every
`CropClassification`, so a prediction can always be traced back to the configuration that
produced it.

## What this doesn't do

- **No calibrated confidence.** Similarity is a raw cosine score against your own examples, not a
  validated accuracy or probability estimate. Temporal weighting affects which identity wins, not
  the confidence number reported for it.
- **No owner-configured identity date ranges.** Removed in v1.5 in favor of automatic per-example
  weighting — see [v1.5-automatic-temporal-classification.md](specs/v1.5-automatic-temporal-classification.md).
- **No retraining.** "Learning" means adding reference examples, not updating model weights.

See [docs/specs/v1.0.0.md](specs/v1.0.0.md) section 8 for the full list of things classification
deliberately doesn't claim.
