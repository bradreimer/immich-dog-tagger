# DT-1110: Add cat support alongside dogs

## **ID**

DT-1110

## **Related spec**

None yet. This ticket is large and cross-cutting -- it touches the schema, detection, the
classification policy, the review API/UI, sync, and Learning Progress metrics. Per this project's
spec-driven workflow (`docs/specs/README.md`), a change of this shape would normally get a spec
first; filed directly as a ticket per the explicit request that created it. Worth writing a spec
before implementation starts if the scope below needs review/discussion first.

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Extend the pipeline and review UI to detect, classify, and review **cats** alongside dogs.
Species is **hardcoded** to `dog` and `cat` (no general-purpose species config). Dog and cat
identities share the same review queue and the same correction UI -- there is no separate tab,
page, or mode for cats.

## **Context**

The project currently assumes every detected/classified/reviewed subject is a dog. The owner also
has cats they want identified using the same detect -> classify -> review -> reclassify -> sync
loop that already exists for dogs. The ML pipeline (YOLO detection, OpenCLIP embeddings,
nearest-neighbor classification) is already species-agnostic; the "dog-only" assumption is baked
into a couple of specific, narrow code paths rather than the model itself:

- **The actual dog-only filter is in crop generation, not YOLO inference.**
  `YOLODetector.detect()` (`src/immich_dog_tagger/yolo_detector.py`) already returns every COCO
  class YOLO finds, unfiltered -- `label` is whatever COCO class name YOLO assigned (`"dog"`,
  `"cat"`, etc. are already available today with zero detector changes). `DetectionService.run()`
  (`src/immich_dog_tagger/services/detection.py`) saves a `Detection` row for every detection
  regardless of label; `detection.label == "dog"` there is only used for a summary counter, not a
  filter. The real, single point of exclusion is `CropWriter.write()`
  (`src/immich_dog_tagger/crops.py:34`): `if detection.label != "dog": continue`. Non-dog
  detections get a `Detection` row but no `Crop`, so they're invisible to everything downstream
  (classification and review both operate on crops). Loosening this one condition to accept both
  `"dog"` and `"cat"` is most of the detection-side change.
- **`Identity.name` is globally unique today**, not scoped per species
  (`src/immich_dog_tagger/models.py`, `Identity.name: Mapped[str] = mapped_column(String(64),
  unique=True, ...)`). A dog "Max" and a cat "Max" would collide under the current constraint.
- **The review page's keyboard shortcuts are already species-agnostic.** They are number keys
  `1`-`9` (`ui/src/features/review/hooks/useReviewKeyboard.ts`), each indexed into whatever
  `identities` array the page passes in (`identities[index]`) -- there's no per-species or
  per-name hardcoding to generalize. Passing a combined dog+cat identity list through is enough;
  no shortcut-scheme redesign is needed.

## **Implementation notes**

### Scope

**In scope:**

- Detect both dogs and cats in the same pipeline run using YOLO's existing `dog` and `cat` COCO
  classes.
- A single photo/asset may contain both a dog and a cat (or multiple of each). Detections are
  **not mutually exclusive** -- take the union of all dog and cat detections found in an asset.
  Each detected crop still belongs to exactly one species (whichever class YOLO assigned to that
  bounding box); the union applies to co-occurring detections within a photo, not to a single crop
  being both.
- Identity classification, review, and reclassify all work identically for cat crops as they do
  for dog crops today -- same confidence threshold (0.80, `ClassifierPolicy.confident_threshold`
  in `policy.py`), same confident/needs-review/unknown states, same nearest-neighbor policy logic.
- The **same review queue and review UI** shows both dog and cat crops together, in the same
  prioritized order (unknown/low-confidence/candidate-conflict), with no species-based tab, filter
  default, or page split. Correction controls (keyboard shortcuts, candidate suggestions) work
  identically regardless of species by construction (see Context) once both species' identities
  flow through the same `identities` list.
- Immich sync creates species-appropriate albums, e.g. `Dog - Hermann` and `Cat - <name>`, instead
  of assuming `Dog -` for everything.
- Identities are species-scoped: a cat identity and a dog identity may share a name without
  colliding.

**Out of scope (explicitly, for this ticket):**

- Generalized/arbitrary species support (birds, rabbits, etc.) -- hardcode `dog` and `cat` only,
  as literal values, not a configurable list.
- Any change to the embedding model or classifier algorithm itself -- cats reuse the existing
  OpenCLIP + nearest-neighbor approach unchanged.
- Per-species confidence thresholds or policy tuning -- cats use the same default threshold and
  the same centralized policy as dogs unless a follow-up ticket says otherwise.
- Renaming the package/CLI/repo (`immich_dog_tagger`, `immich-dog-tagger`) -- tracked separately
  if desired.

### Design

**Data model** -- add a `species` field (`"dog"` | `"cat"`, hardcoded enum/literal, not free-text
or config-driven) to `Crop` (or `Detection`, which already effectively carries it via `label` --
worth deciding whether to derive from `Detection.label` or duplicate onto `Crop`/
`CropClassification` for query convenience) and to `Identity`. Change `Identity`'s uniqueness
constraint from `name` alone to `(species, name)`. Existing rows backfill to `species = "dog"` via
an additive migration (follow the `_ensure_*` pattern already used in `database.py`) -- behavior-
preserving for existing projects, not a breaking change.

**Detection (`detect`)** -- change `CropWriter.write()`'s filter from `label != "dog"` to exclude
neither `"dog"` nor `"cat"`. Tag each `Crop` (or derive from its `Detection`) with `species`. No
change to crop generation mechanics, image caching, or storage layout beyond that.

**Classification (`classify` / Reclassify)** -- nearest-neighbor search for a given crop must be
scoped to reference examples of the **same species** -- a cat crop should never be compared
against dog reference examples, and vice versa. This is the main behavioral change beyond
plumbing: candidate ranking, confidence scoring, and the confident/needs-review/unknown decision
in `policy.py` all need a `species` parameter (or equivalent scoping) threaded through. Reclassify's
existing guarantees (idempotent, never touches confirmed labels, safe to re-run) must hold
identically for cat crops.

**Review UI / API** -- `GET /review`, `GET /review/stats`, `POST /classifications/{id}/correct`,
`POST /review/{id}/skip` should either already be species-neutral because they operate on crop/
classification IDs, or be updated so filtering/stats aggregate across both species by default
while still being able to report species-specific counts for Learning Progress. The review queue
itself is **unified** -- no `?species=` filter is required by this ticket for basic display,
though the existing filter mechanism (unknown / low-confidence / candidate-conflict) should
continue to work across both species without a species toggle. If a species filter is desired
later, that's a follow-up (see Open questions).

**Sync** -- `immich-dog-tagger sync` creates/updates albums per identity using a species-aware
label, e.g. `Cat - <name>` instead of assuming `Dog -` for every album.

**Learning Progress** -- coverage, review rate, and labeled-example counts should be reportable
per species (at minimum, don't silently mix dog and cat counts into one misleading number) even
though the review UI itself stays unified.

### Suggested implementation order

1. Schema migration: add `species` to `Crop`/`Detection` and `Identity`, scoped `(species, name)`
   uniqueness, backfill existing rows to `"dog"`.
2. Detection: loosen `CropWriter.write()`'s class filter to keep `cat` alongside `dog`; tag crops
   with species.
3. Classification/policy: thread `species` through nearest-neighbor search and `policy.py`
   decision logic.
4. Reclassify: verify species-scoping holds under existing idempotency guarantees; extend tests.
5. Review API/UI: verify the unified queue and existing filters work across both species; confirm
   the identity list passed to `useReviewKeyboard` already covers both (see Context -- likely no
   shortcut-scheme change needed, just data flow).
6. Sync: species-aware album naming.
7. Learning Progress: per-species metrics.
8. End-to-end regression tests covering a mixed dog/cat project (detect -> classify -> review ->
   reclassify -> sync).

## **Acceptance criteria**

1. Running the pipeline on a library containing both dogs and cats produces crops and
   classifications for both species in a single pass.
2. A photo containing one dog and one cat produces two crops (one per species) via the union of
   detections; both are classified independently.
3. A cat crop is never suggested a dog identity as a candidate, and vice versa.
4. The Review page shows dog and cat items together in one queue, sorted by the existing priority
   rules, with no separate cat tab/page.
5. Keyboard-shortcut correction and the correction UI work identically for cat items as for dog
   items.
6. Reclassify run on a mixed dog/cat project is idempotent and species-scoped (running it twice
   with no new reviews produces 0 changed predictions for both species).
7. Sync produces correctly labeled Immich albums for both dogs and cats.
8. Existing dog-only projects continue to work unchanged after migration (backward compatible).
9. Two identities with the same name but different species (e.g. dog "Max" and cat "Max") do not
   collide or get merged.

## **Testing requirements**

- Migration test (matching the existing `_ensure_*` pattern in `tests/test_database.py`)
  confirming existing databases upgrade cleanly with all existing detections/identities backfilled
  to `species = "dog"`, and that `(species, name)` uniqueness is enforced going forward.
- Detection service test: an asset with both a dog and a cat detection produces two `Crop` rows,
  correctly species-tagged; a non-dog/cat COCO detection (e.g. "person") still produces no crop.
- Classifier/policy tests: nearest-neighbor search never returns a cross-species candidate, using
  a fixture with both dog and cat reference examples whose embeddings would otherwise be each
  other's nearest neighbor if species scoping were broken.
- Reclassify idempotency test extended to a mixed dog/cat fixture (acceptance criterion 6).
- API test: `GET /review` on a mixed fixture returns both species interleaved by the existing
  priority rules, not grouped or filtered by species.
- Sync test: album naming for a cat identity produces `Cat - <name>`, not `Dog - <name>`.
- E2E regression test extending the existing review-driven learning loop suite
  (`tests/test_e2e_review_learning_loop.py`) to a mixed dog/cat project end to end.

## **Dependencies**

None -- builds on the existing detection/classification/review/sync pipeline; no other pending
ticket blocks it.

## **Suggested commit message**

`feat(DT-1110): add cat support alongside dogs`

(Likely to land as several commits following the suggested implementation order above rather than
one -- schema migration, detection, classification/policy, review, sync, and metrics are each
independently testable slices.)

## **Open questions for follow-up tickets (not blocking this one)**

- Should the review queue eventually support an optional species filter?
- Do cat identities need their own confidence threshold given potentially different embedding
  separability than dogs?
