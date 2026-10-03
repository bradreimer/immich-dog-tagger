# ADR-012: Open-vocabulary detector for per-photo "Look harder"

## Status

Accepted. Implements [#390](https://github.com/bradreimer/immich-dog-tagger/issues/390).

## Context

Detection (YOLO11m, COCO-trained) and matching (OpenCLIP ViT-B-32) are separate models joined only
by the crop. When YOLO misses a dog, the per-photo Repair action re-runs YOLO and misses it again.

Owners repairing a single photo will wait 1–5 minutes for a better result. That budget allows a
detector too slow for the batch pipeline but practical on CPU for one image.

## Decision

- Add **Grounding DINO** (`IDEA-Research/grounding-dino-base`, Apache-2.0) as a second
  `ObjectDetector`, `GroundingDinoDetector`, loaded through Hugging Face `transformers`. It's
  prompted with "a dog. a cat." and emits the same `DetectionResult` shape, labeled `dog` or `cat`.
  `LOOK_HARDER_MODEL` overrides the model id or points at a local copy.
- Use it only from the per-photo **Look harder** action on Photo Lookup. Repair and the batch
  pipeline keep YOLO.
- Run Look harder as a `look_harder` pipeline job targeting one photo
  (`PipelineJob.target_immich_asset_id`), reusing `AssetRepairService` with the alternate detector.
- Record provenance in a new `Detection.detector` column (`yolo` or `grounding_dino`), backfilled
  to `yolo`. A batch `detect --force` skips photos with non-YOLO detections.
- Make `transformers` a regular dependency. It's pure Python and reuses the `torch` that
  `ultralytics` and `open-clip-torch` already install. Load the model lazily on first use, never at
  API startup. Weights are cached under `HF_HOME` (the models volume in Docker Compose).

## Alternatives considered

- **OWLv2.** Also open-vocabulary and Apache-2.0. Slower on CPU at its native resolution, with no
  clear accuracy advantage for a single well-known class like "dog".
- **A larger YOLO, higher resolution, test-time augmentation, or tiling.** Cheaper, but the same
  model family tends to miss the same dogs. Out of scope for this action; may be added later.
- **Synchronous request, like Repair.** Several minutes exceeds typical reverse-proxy timeouts.
- **An optional dependency extra.** The Docker image installs only default dependencies, so the
  feature would be unavailable in the standard deployment.

## Consequences

- The first Look harder downloads about 900 MB of weights. Later runs load from the cache.
- Peak memory rises by roughly 1–2 GB while the model is loaded. It stays loaded for the life of
  the process after first use.
- Look harder shares the single job queue, so it waits behind a running pipeline job.
- Detection rows now carry their detector, which future detector changes can build on.
