# ADR-010: Dog re-identification embedding model replaces OpenCLIP

## Status

Accepted.

## Context

Classification (`docs/ml-classification.md`) is entirely nearest-neighbor matching in embedding
space: `IdentityClassifier` computes cosine similarity between a crop's embedding and every stored
`EmbeddingExample`, weights it by temporal/spatial recency (ADR-003, ADR-007), and ranks identities.
Every downstream piece -- `ClassifierPolicy`'s confidence threshold, the review queue, Reclassify,
Learning -- treats that similarity number as ground truth about how alike two crops are. None of it
can be better than the embedding space it's built on.

`OpenClipEmbedder` used `open_clip`'s `ViT-B-32` / `laion2b_s34b_b79k` weights: a general
image-text CLIP model trained so that an image's embedding sits close to a caption describing it.
That objective clusters images by *what's depicted* ("a photo of a dog," a breed, a setting) far
more strongly than it separates *which individual* is depicted -- CLIP was never trained on
individual-identity labels. Two different same-breed dogs photographed in similar lighting can sit
closer together in CLIP space than two photos of the same dog taken years apart. Since the
classifier's entire decision is "which stored example is this crop closest to," a space that isn't
optimized to separate individuals puts a ceiling on accuracy no amount of tuning downstream
(threshold, temporal/spatial weighting) can lift.

## Decision

Replace `OpenClipEmbedder` with a new `DogReIDEmbedder`
(`src/immich_dog_tagger/dog_reid_embedder.py`), backed by **MegaDescriptor-L-384**
(`hf-hub:BVRA/MegaDescriptor-L-384`, loaded via `timm`), a Swin-Large backbone trained with metric
learning (ArcFace-style) specifically for individual animal re-identification, across ~30
individual-identity datasets spanning many species -- including dog face/individual-identity data
(the training corpus behind MegaDescriptor and the WildlifeReID-10k benchmark it's evaluated on
draws on datasets such as DogFaceNet). Unlike CLIP, its training objective is explicitly "pull
together images of the same individual, push apart images of different individuals" -- the exact
property the classifier depends on.

It replaces `OpenClipEmbedder` behind the existing `Embedder` protocol
(`src/immich_dog_tagger/embedder.py`) with no change to its interface (`embed`/`embed_batch`,
L2-normalized `float32` vectors) -- `IdentityClassifier`, `ClassifierPolicy`, `scoring.py`, and
every service that consumes an embedding stay untouched. `EmbeddingExample.embedding` and
`CropClassification.embedding` are already stored as raw bytes with no fixed dimensionality
assumption anywhere in the codebase (`embeddings.py`'s `blob_to_embedding`/`embedding_to_blob`
round-trip via `np.frombuffer`/`.tobytes()`), so the model swap needs no schema change to the vector
column itself.

What the swap does require: a stored vector is only meaningful compared against another vector from
the *same* model, and MegaDescriptor's embedding dimensionality (1536) differs from CLIP ViT-B-32's
(512). Every `EmbeddingExample` and `CropClassification` row written under OpenCLIP becomes stale
the moment the embedder changes -- comparing an old vector to a new one is meaningless at best and
a shape-mismatch crash at worst. This ADR pairs the model swap with:

- An `embedding_model` column on both tables (additive migration, `database.py`'s existing
  `_ensure_*` pattern), so a stored vector is traceable to what produced it, the same way
  `CropClassification.classifier_version` already traces a prediction to the policy that produced
  it.
- A `reembed` operation (`services/reembed.py`) that recomputes every stored vector from its source
  image under the current embedder and re-stamps `embedding_model`, then runs the existing,
  unmodified `ReclassifyService`. `reembed` touches only embedding vectors, never
  `identity`/`confidence`/`source` -- so it cannot violate "reclassification never mutates reviewed
  labels" (ADR-009's contract, `docs/ml-classification.md`), and `Reclassify` continues to only ever
  touch AUTO-sourced rows exactly as it already does. See
  [docs/specs/dog-reid-embeddings.md](../specs/dog-reid-embeddings.md) for the full requirements.

Model weights are fetched once from the Hugging Face Hub on first use and cached locally by
`timm`/`huggingface_hub`, exactly like `open_clip`'s previous pretrained-weight download and
`YOLODetector`'s model file. No image data or crop ever leaves the machine -- only the one-time,
public model-weight download reaches the network, same category of exception the project's
local-first principle already carves out for YOLO/OpenCLIP weights.

## Alternatives considered

- **Keep OpenCLIP, tune the threshold/temporal/spatial weighting further.** Rejected: those knobs
  only reweight an already-computed similarity; they cannot fix an embedding space that wasn't
  trained to separate individuals in the first place. `docs/ml-classification.md`'s "No calibrated
  confidence" section already documents that similarity is a raw, uncalibrated score -- the fix
  belongs in the embedding space, not in post-hoc weighting.
- **Fine-tune our own model on this project's `EmbeddingExample` history.** More accurate in
  principle (trained on this project's actual dogs), but out of scope here: it needs a training
  pipeline, GPU time, and a meaningfully sized labeled corpus this project doesn't yet have for most
  installs (the corpus grows from review, and review only starts producing volume after
  classification is already running). Left for `docs/roadmap.md`'s Active Learning Improvements as
  a follow-up once there's a large enough reviewed corpus to fine-tune on; the spec's Non-goals
  records this explicitly.
- **A different off-the-shelf face-recognition model (dlib/FaceNet-style human face embeddings).**
  Rejected: trained on human face geometry, which does not transfer to dog faces/coats, and the
  project doesn't need face-only re-id -- crops include the whole dog, and coat pattern is often as
  identity-discriminative as the face.
  A narrower, dog-only face-recognition model (e.g. a `DogFaceNet`-style CNN trained solely on dog
  faces) was also considered; MegaDescriptor was preferred because it's a maintained, benchmarked,
  off-the-shelf checkpoint (no training run of our own to reproduce) whose evaluation already
  includes dog-identity data, and because coat-based re-id (not just face) matters for crops that
  don't show a clean frontal face.
- **A smaller MegaDescriptor variant (`-S-224` or `-B-224`) for lower resource use.** Left as a
  possible future tuning knob rather than the initial choice: this project doesn't yet have a
  config surface for the embedding backbone (spec Non-goals), and `-L-384` is the variant
  MegaDescriptor's own benchmarks show winning by the widest margin. If CPU-only deployments prove
  the larger backbone too slow in practice, swapping to a smaller variant is a one-line change
  inside `DogReIDEmbedder`, not an architectural one.
- **Making the embedding backbone configurable now (env var/settings page).** Rejected for this
  change: no second backbone exists yet to choose between, and a config surface for a choice with
  only one option adds complexity with no present benefit (spec Non-goals). Revisit if/when a
  second backbone is actually on the table.

## Consequences

- Every embedding computed from here on is a re-identification embedding, not a CLIP embedding --
  classification accuracy should improve for the exact case that motivated this change
  (distinguishing individuals, not just species/breed), per MegaDescriptor's own published
  re-identification benchmarks (this project has no offline accuracy-comparison harness of its own;
  see the spec's Open questions).
- Existing installs must run `reembed` once after upgrading, or their stored vectors stay in the
  old (smaller-dimension, differently-trained) space and cannot be meaningfully compared against
  anything embedded after the upgrade. This is a manual, owner-triggered step (spec Non-goals/Open
  questions), consistent with every other resource-heavy pipeline operation in this project.
- `timm` and its Hugging Face Hub download path become new dependencies; `open-clip-torch` is
  removed. `torch`/`torchvision` stay (already required by YOLO and the previous OpenCLIP embedder).
- MegaDescriptor-L-384 (Swin-Large) is heavier than ViT-B-32; embedding throughput on CPU-only
  deployments may be slower. No resource budget regression tests exist for this pipeline stage
  today (same gap DT-1008 already documented for the pipeline generally), so this is a qualitative,
  not measured, consequence.
