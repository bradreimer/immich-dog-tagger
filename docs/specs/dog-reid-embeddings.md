# Dog re-ID embeddings

## Purpose

Replace OpenCLIP as the embedding backbone behind classification with a model purpose-built for
individual animal re-identification, to improve classification accuracy without changing anything
about the classifier, policy, or review workflow built on top of embeddings.

## User story

As the owner reviewing predictions, I want the classifier to tell visually similar dogs apart more
reliably (littermates, same-breed dogs, dogs photographed in similar settings/lighting), so that
fewer correct predictions get demoted to needs-review and fewer wrong predictions get shown as
confident, without me doing any extra work beyond what the review workflow already asks of me.

## Context

`OpenClipEmbedder` (`src/immich_dog_tagger/openclip_embedder.py`) embeds every crop with
`open_clip`'s `ViT-B-32` / `laion2b_s34b_b79k` weights -- a general image-text CLIP model. CLIP's
embedding space is trained to align images with captions, not to separate individuals of the same
species/breed: it clusters "a photo of a dog" together and is not optimized to place two different
golden retrievers far apart while placing two photos of the *same* golden retriever close together.
`IdentityClassifier` (`docs/ml-classification.md`) does nearest-neighbor matching entirely on
cosine similarity in this space, so classification accuracy is bounded by how discriminative the
embedding space is for individual dog identity, not just breed/species.

Nothing about the pipeline downstream of the embedding vector -- `IdentityClassifier`,
`ClassifierPolicy`, temporal/spatial weighting, the review queue, Reclassify, Learning -- assumes
anything about the embedding model beyond "cosine similarity between two vectors of the same
dimensionality measures how alike two crops are." That boundary is what makes this a model swap,
not a redesign: see [ADR-010](adr/ADR-010-dog-reid-embedding-model.md) for the model choice and why
the swap is scoped the way it is.

## Goals

- Replace `OpenClipEmbedder` with a dog re-identification embedding model, fine-tuned via metric
  learning on individual-level animal identity data (including dog faces/coats), behind the
  existing `Embedder` protocol (`src/immich_dog_tagger/embedder.py`).
- Stay local-first (ADR-010, project privacy principle): the model runs fully offline against local
  crop images; only its own public weights are fetched once, the same way YOLO and the previous
  OpenCLIP weights already are.
- Recognize that an embedding vector is only comparable to another vector from the *same* model.
  Track which model produced each stored vector (`embedding_model` on `EmbeddingExample` and
  `CropClassification`), and provide a migration path (`reembed`) that recomputes every stored
  vector under the new model without touching any human-reviewed identity label.
- Keep the classifier, policy, and review workflow completely unaware of which embedding model is
  in use -- this is a swap behind `Embedder`, not a redesign of any of those layers.

## Non-goals

- Fine-tuning a model on this project's own reviewed corpus (`EmbeddingExample` history). The
  chosen model is used as shipped; training our own weights from the accumulating review history is
  a separate, larger idea for `docs/roadmap.md`'s Active Learning Improvements section.
- A configurable/pluggable choice of embedding backbone (env var, settings page). One embedder is
  wired in, as `OpenClipEmbedder` was; making it swappable is deferred until there's a concrete
  second backbone to choose between.
- A dedicated UI workspace for the re-embed migration beyond the existing Overview "Manual
  Operations" card entry and Job Queue progress reporting every other pipeline operation already
  gets.
- Automatically re-running `reembed` on deploy. It is an explicit, owner-triggered operation (see
  Open questions), like every other pipeline stage.
- Repairing crops whose files are missing from `CACHE_DIR` at re-embed time. That's
  `docs/specs/broken-crop-auto-repair.md`'s job; `reembed` skips and counts them, the same
  isolate-and-continue treatment `ClassificationService`/`ReclassifyService` already give a missing
  crop file elsewhere in the pipeline.

## Requirements

1. **FR-1**: A new `Embedder`-conforming class embeds a crop image into an L2-normalized float32
   vector using a dog re-identification model (ADR-010), replacing `OpenClipEmbedder` everywhere it
   was constructed (`runtime.get_embedder()`, and any direct instantiation).
2. **FR-2**: `EmbeddingExample.embedding_model` and `CropClassification.embedding_model` record
   which model produced the stored vector. Existing rows are backfilled with a sentinel identifying
   the prior OpenCLIP model (additive migration, following `database.py`'s existing `_ensure_*`
   pattern); every new write stamps the embedder's own model id.
3. **FR-3**: A `reembed` pipeline operation recomputes every `EmbeddingExample.embedding` (from its
   `crop_path`) and every `CropClassification.embedding` (from its crop's cached image) under the
   current embedder, stamping `embedding_model`. It never changes `identity`, `confidence`,
   `source`, or any other label-bearing field -- only the vector and its model stamp -- so it never
   conflicts with the "reclassification never mutates reviewed labels" rule
   (`docs/ml-classification.md`, ADR-009's contract). A crop whose cached file is missing is skipped
   and counted, not treated as a fatal error for the run.
4. **FR-4**: `reembed` is followed by a normal `Reclassify` pass (same job) so AUTO predictions
   catch up to the recomputed vectors using the existing, unmodified `ReclassifyService` -- no new
   classification logic.
5. **FR-5**: `reembed` is triggerable the same way every other pipeline operation is: as a
   `PipelineOperation` job (`POST /jobs`), from the CLI/job system, and from Overview's Manual
   Operations card, with the same progress reporting (Job Queue) every other operation gets.
6. **FR-6**: No behavior change to `IdentityClassifier`, `ClassifierPolicy`, `scoring.py`, the
   review queue, Learning, or Sync -- they operate on whatever fixed-length vector they're handed,
   unaware of which model produced it.

## Acceptance criteria

- Given a fresh install, classification runs end to end using the new embedder with no
  configuration beyond what OpenCLIP required (weights fetched once, cached locally, no other
  network use).
- Given an existing `state.db` with OpenCLIP-era `EmbeddingExample` and `CropClassification` rows,
  running `reembed` recomputes every vector's embedding and stamps `embedding_model` with the new
  model's id, without changing any `EmbeddingExample.identity_id` or any
  `CropClassification.identity`/`confidence`/`source` for a REVIEW/MANUAL-sourced row.
- Given `reembed` has run, a subsequent Reclassify pass produces predictions computed entirely in
  the new embedding space (no mixed-dimension comparison between an old and a new vector).
- Given a crop whose cached file no longer exists on disk, `reembed` skips it, logs a warning, and
  reports it in the operation's summary count rather than failing the whole run.
- `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and the UI's
  `npm run build` / `npm run lint` / `npm test` all pass.

## Open questions

- Whether `reembed` should run once automatically the first time the app starts after this ships
  (detecting any row whose `embedding_model` is the legacy sentinel), or stay a manual,
  owner-triggered operation like every other pipeline stage. This spec keeps it manual (see
  Non-goals) since an unattended full re-embed + reclassify pass on a large library is exactly the
  kind of resource-heavy, potentially long-running operation this project otherwise always leaves
  to an explicit trigger (full_pipeline, reclassify, sync all work the same way); revisit if that
  turns out to be confusing in practice.
- Whether classification accuracy actually improves in practice is not something this change can
  prove from inside the codebase -- it rests on the embedding model's own published re-identification
  benchmarks (ADR-010). No offline accuracy-comparison harness exists in this project today; adding
  one (e.g. held-out review-corpus evaluation) is future work, not scoped here.
