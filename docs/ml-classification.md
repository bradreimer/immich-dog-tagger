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

## Image decoding

Every image the pipeline decodes goes through `open_upright()`
(`src/immich_dog_tagger/images.py`), which applies the source photo's EXIF
orientation. Detection, cropping, and embedding have to agree on one pixel
coordinate space -- a detector box is meaningless to the cropper otherwise --
and they only do if they decode identically. Decode images through that helper
rather than calling `PIL.Image.open` directly; see
[#137](https://github.com/bradreimer/immich-dog-tagger/issues/137) for what
went wrong when they diverged. HEIC needs one extra step: pi-heif's Pillow
plugin resets the Orientation tag it exposes via `getexif()` to 1 on decode
without rotating the pixels, stashing the real value under
`image.info["original_orientation"]` instead -- `open_upright()` copies that
back before transposing. See
[#191](https://github.com/bradreimer/immich-dog-tagger/issues/191).

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
   date is missing on either side) — see [ADR-003](adr/ADR-003-automatic-temporal-recency-classification.md)
   — and by how close its own location is to the crop's (`spatial_weight`, a Gaussian decay with a
   ~2km scale, fails open when a coordinate is missing on either side) — see
   [ADR-007](adr/ADR-007-automatic-spatial-proximity-classification.md).
4. Keeps each identity's best-matching example by that *weighted* score (similarity × temporal
   weight × spatial weight), then ranks identities the same way — but reports the winning match's
   raw, unweighted similarity as confidence, so recency and location decide which identity wins
   without inflating or discounting the number shown.
5. Returns the top candidates (3 by default), not just the winner.

**`ClassifierPolicy`** (`src/immich_dog_tagger/policy.py`) is the single place that owns the
confidence threshold (0.80 by default), candidate-list size, and the confident/needs-review/unknown
decision. The pipeline, `Reclassify`, and the review queue all read from it, so the meaning of
"confident" is the same everywhere it appears. The policy version is stored alongside every
`CropClassification`, so a prediction can always be traced back to the configuration that
produced it.

## Clustering is not classification

`clustering.py` and `services/clusters.py` (issue #141) group one pet's *pending recommendations*
into sets of visually similar crops, so the owner can approve a whole set in one action from the
Library. It sits beside classification, not inside it:

- It is a **read**. It writes no prediction, no confidence and no identity; running it twice with
  no approvals in between changes no rows.
- It uses **agglomerative average-linkage clustering over cosine distance**, computed on demand
  over the embeddings already stored on `CropClassification`. Ties break by lowest index, so the
  same pool always produces the same groups.
- Its distance cut (0.20 cosine distance) is a **grouping knob owned by `clustering.py`**, not a
  classification threshold. It never reads or writes `ClassifierPolicy`: it answers "do these
  photos look alike enough to show as one group?", not "is this the pet?".
- Approving a cluster is **N ordinary corrections** through `ClassificationCorrectionService`, so
  an approval leaves exactly the review actions, reference examples and provenance that N single
  reviews would.

## What this doesn't do

- **No calibrated confidence.** Similarity is a raw cosine score against your own examples, not a
  validated accuracy or probability estimate. Temporal weighting affects which identity wins, not
  the confidence number reported for it.
- **No owner-configured identity date ranges.** Removed in v1.5 in favor of automatic per-example
  weighting — see [v1.5-automatic-temporal-classification.md](specs/v1.5-automatic-temporal-classification.md).
- **No retraining.** "Learning" means adding reference examples, not updating model weights.
- **No identity from clustering.** A cluster is a proposal about visual similarity; only a human
  approval settles who is in a photo.

See [docs/specs/v1.0.0.md](specs/v1.0.0.md) section 8 for the full list of things classification
deliberately doesn't claim.
