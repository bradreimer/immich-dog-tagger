# ADR-011: Restore OpenCLIP as the embedding model

## Status

Accepted. Supersedes the model choice in [ADR-010](ADR-010-dog-reid-embedding-model.md). ADR-010's
`embedding_model` tracking and `reembed` operation stay in place.

## Context

ADR-010 replaced OpenCLIP (`ViT-B-32` / `laion2b_s34b_b79k`) with MegaDescriptor-L-384 because
MegaDescriptor is trained for individual animal re-identification. ADR-010 noted that the project
had no way to measure whether accuracy actually improved.

On a real library ([#377](https://github.com/bradreimer/immich-dog-tagger/issues/377)), the
result after Re-embed was a collapse, not an improvement:

- Confidently classified crops fell from about 10,400 to 586. Needs Review rose to about 10,300.
- Best-match similarity for unreviewed crops centered on 0.2–0.4, far below the 0.80 confident
  threshold.

A leave-one-out check over 4,693 reviewed examples showed that lowering the threshold would not
help. For each example, the check hides it, finds its nearest other example, and records whether
that example is the same dog:

| Nearest match may come from | Top-1 accuracy | Auto-tagged at 0.80 | Correct at 0.80 |
|---|---|---|---|
| Any other example | 77.9% | 28.7% | 98.3% |
| A different day only | 49.4% | 2.4% | 90.4% |

The "different day" row matches real use: a new photo rarely has a near-duplicate from the same
moment among the reviewed examples. MegaDescriptor mostly matched photos from the same shoot (same
light, background, and pose) and could not recognize the same dog on another day. It was trained
largely on wildlife and camera-trap data, which differs from home pet photos.

Before the switch, OpenCLIP was confidently tagging about 10,000 crops on the same library.

## Decision

Restore `OpenClipEmbedder` (`src/immich_dog_tagger/openclip_embedder.py`) as the embedder that
`runtime.get_embedder()` returns, and remove `DogReIDEmbedder`.

`OpenClipEmbedder.MODEL_ID` equals `LEGACY_OPENCLIP_MODEL_ID`, the stamp the ADR-010 migration
gave every pre-MegaDescriptor vector. Any vector that was never re-embedded is directly comparable
with new ones again. Owners run `reembed` once to recompute the MegaDescriptor vectors with
OpenCLIP. As before, `reembed` changes only vectors and their stamp, never identities, reviews, or
examples.

## Alternatives considered

- **Keep MegaDescriptor with a lower, per-model threshold.** Rejected: at any threshold that tags
  a useful share of crops on the different-day test, accuracy is 50–70%.
- **Keep both models and combine their scores.** Rejected for now: more complexity and compute
  for a model that has not shown it adds signal on this kind of library.
- **Try another re-identification model.** Possible future work, but it needs the same
  leave-one-out check, run against OpenCLIP as a baseline, before it replaces OpenCLIP again.

## Consequences

- Classification returns to the accuracy owners saw before ADR-010. Owners who ran Re-embed under
  MegaDescriptor must run `reembed` once more after upgrading.
- `open-clip-torch` returns as a dependency. `timm` is no longer a direct dependency.
- Future embedding-model changes should be backed by a measured comparison on a real reviewed
  library, using the different-day leave-one-out test above, not only by published benchmarks.
