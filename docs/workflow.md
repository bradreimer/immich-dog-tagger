# New Project Workflow

This is the operator-facing guide for taking a project from an empty database to
progressively better automatic dog identification, using the v1.0.0 review ->
reclassify loop. It assumes no machine-learning background.

## 1. First-project setup

1. Configure `.env` (see [README.md](../README.md#quick-start)): `IMMICH_URL`,
   `IMMICH_API_KEY`, `STATE_DIR`, `CACHE_DIR`, `YOLO_MODEL`, and — when your browser reaches
   Immich at a different address than this app's backend does — `IMMICH_EXTERNAL_URL`.
2. Initialize the database: `immich-dog-tagger init-db` (or just run the pipeline --
   it creates the database on first use).
3. Run the full pipeline once: `immich-dog-tagger pipeline`, or from Mission
   Control click **Process new photos**. This scans Immich, downloads new
   assets, detects dogs, and classifies every detected crop.
4. With zero labeled examples, every crop will classify as **Unknown**. This is
   expected -- see [Confidence, needs-review, and unknown](#3-confidence-needs-review-and-unknown)
   below. Nothing in the system forces a label onto a crop it can't support.

## 2. The initial review batch: 50-100 items, not a magic number

Open the **Review** page and correct 50-100 items. This range is a *starting
point*, not a threshold the system enforces or checks for:

- Fewer than ~50 reviews usually means too few reference examples per dog for
  the nearest-neighbor classifier to distinguish between similar-looking dogs
  confidently.
- There's no hard ceiling. Review more if you have a lot of dogs, fewer photos
  covering a wider variety of angles/lighting, or dogs that look similar to each
  other. Review less if you have very few dogs and abundant, easy examples.
- The **Learning Progress** card on the Metrics tab (labeled-example count,
  confident coverage) is the actual signal to watch, not a review counter.

Every correction you make (accept, correct, or mark Unknown) becomes ground
truth immediately and, for a named identity, a new reference example -- see
[docs/ml-classification.md](ml-classification.md) for how the classifier uses
these examples.

## 3. When to click Reclassify

**Reclassify** (Overview -> Manual Operations) recomputes predictions
for existing crops using your current set of reviewed examples. Click it:

- After finishing a review batch, to see how much the new examples improved
  automatic classification.
- Any time the **Learning Progress** card's confident-coverage number looks
  stale relative to how much you've reviewed since the last pass.
- As often as you like -- it's safe to run repeatedly. It never rescans,
  redownloads, or redetects photos, and it never changes a label you've
  already confirmed through review. Running it twice in a row with no new
  reviews in between produces identical results (0 changed predictions).

It does **not** replace running the pipeline on new photos -- Reclassify only
touches crops that already exist in the database.

## 4. Confidence, needs-review, and unknown

Every automatic prediction is one of three states, decided by one centralized
policy (`src/immich_dog_tagger/policy.py`) so the meaning is the same
everywhere it appears (Review queue, Reclassify, Learning Progress):

| State | Meaning |
|---|---|
| **Confident** | The best-matching reference example is similar enough (>= the confidence threshold, 0.80 by default) that the system assigns that identity automatically. |
| **Needs review** | A candidate identity exists, but the match isn't similar enough to trust automatically. Shown in the Review queue for a decision. |
| **Unknown** | No candidate was similar enough to suggest an identity at all -- most commonly the very first pass, before any examples exist for a dog, or a genuinely unfamiliar dog. |

None of these is "accuracy" or a calibrated probability. It's a similarity
score against your own reviewed examples -- see the "Classification semantics"
non-goals in [docs/specs/v1.0.0.md](specs/v1.0.0.md) for what v1.0.0
deliberately does not claim.

## 5. The iterative workflow

```
New project
  -> Pipeline (scan/download/detect/classify)
  -> Review 50-100 items
  -> Reclassify
  -> Review remaining uncertain results
  -> Reclassify
  -> Repeat
```

Each cycle should need fewer manual corrections than the last, visible on
the Metrics tab as confident coverage trending up and the review queue
shrinking. When new photos arrive later, just run the pipeline again (or let a
schedule do it -- see [docs/deployment.md](deployment.md#unattended-operation))
and repeat the review -> reclassify loop for anything it can't classify
confidently.

## 6. Backups, state, and recovery

`state.db` is the only thing in this system that cannot be regenerated --
downloaded assets and crops can always be rebuilt from Immich, but review
history and learned examples cannot. Treat it accordingly:

- **Back up**: `immich-dog-tagger backup` creates a consistent SQLite backup
  and reports its path, size, and timestamp.
- **Validate**: `immich-dog-tagger validate-backup <path>` confirms a backup
  file is a readable, valid SQLite database before you trust it.
- **Restore**: `immich-dog-tagger restore <path>` replaces the active database
  with a validated backup. It is explicit and always creates a rollback copy
  of the current database first -- it never silently overwrites state.
- **Rebuild derived data**: `immich-dog-tagger check-derived-data` reports any
  missing downloads/crops/embedding sources and prints rebuild guidance.
  Derived data (downloads, crops) is safe to delete and regenerate; `state.db`
  is not.
- **Operational visibility**: Overview's diagnostics panel and the
  `/diagnostics` API report database health, scheduler health, stuck/failed
  jobs, last backup time, and derived-data completeness in one place.

Back up before any risky operation (a restore, a manual database edit, an
upgrade you're unsure about) and on a regular schedule for an actively used
project.

## 7. Regenerating crops after the image-orientation fix

Applies only to projects that ran a version before the EXIF-orientation fix
([#137](https://github.com/bradreimer/immich-dog-tagger/issues/137)). Skip
this if you started on a version that includes it.

Before the fix, photos carrying an EXIF orientation tag (most phone photos not
shot in the sensor's native landscape orientation) were cropped in the wrong
coordinate space: the crop came from the wrong region of the photo and was
saved rotated. Those crop files stay wrong until they are regenerated, and the
embeddings computed from them stay stale.

Nothing is regenerated automatically -- the fix changes how new crops are
written, it does not rewrite existing data. Regenerate deliberately:

1. **Back up first**: `immich-dog-tagger backup`.
2. **Re-run the pipeline with `--force`**:
   `immich-dog-tagger pipeline --force`. This is the one command that does the
   whole job: `--force` re-downloads the originals, re-detects, re-crops, and
   classifies the regenerated crops. Re-downloading is not optional -- detection
   deletes each cached original once crops exist, so there is nothing left on
   disk to re-crop from.

Expect this to take about as long as the initial import: it re-fetches and
re-runs detection over the whole library.

What survives and what doesn't:

- **Your review decisions survive.** The identity labels you confirmed are
  human ground truth in `state.db` and are not touched by any of this.
- **`EmbeddingExample` rows survive**, and keep pointing at the same crop
  filenames -- `crop_path` is a path, not a foreign key. But an example added
  before the fix stores an embedding computed from the *rotated* crop, so it no
  longer describes the file it now names. There is no command that re-embeds
  existing examples; correcting a few items in the review queue is the
  practical way to seed upright reference examples for an identity.
- **Detection, crop, and classification rows are recreated** with new ids.

Regenerating is not urgent for a library that is already classifying well: the
rotated crops were at least *consistently* rotated, so the reference set and
the crops matched against it shared the same distortion. The gain is accuracy
on newly added photos, which are now upright while pre-fix examples are not --
which also means a library with many pre-fix examples benefits from doing this
sooner rather than accumulating more of them.

## 8. Known v1.0.0 limitations

- **No temporal weighting.** A photo's capture date is stored and shown as
  context on matched examples, but it does not influence classification --
  an old photo and a new one of the same dog are weighted identically.
- **No separate training step.** There is no model retraining; the classifier
  is a fixed embedding model plus nearest-neighbor search against your
  reviewed examples. "Learning" means growing that example set, not updating
  model weights.
- **No calibrated probabilities.** Confidence is a cosine-similarity score
  against your own examples, not a validated accuracy/probability estimate --
  see [docs/specs/v1.0.0.md](specs/v1.0.0.md) section 8 for the full list of
  explicit v1.0.0 non-goals (personalized per-dog neural classifiers, fully
  autonomous labeling with no review path, distributed/cloud-scale
  orchestration, and others).
- **Single active operation at a time.** The job system runs one pipeline or
  Reclassify operation at a time by design (see
  [DT-1005: Job lifecycle, idempotency, and recovery](https://github.com/bradreimer/immich-dog-tagger/issues/50));
  queue another operation and it waits rather than running concurrently.
