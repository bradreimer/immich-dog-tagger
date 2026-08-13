# DT-1114: Date-aware classification and impossible-prediction flagging

## **ID**

DT-1114

## **Related spec**

[v1.4-trustworthy-photo-library.md](../specs/v1.4-trustworthy-photo-library.md) (FR-4, FR-5)

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Use a photo's capture date as an additional classification signal: when an identity has a known
active date range, flag (never silently accept) a candidate match whose active range can't
include the photo's capture date. This is particularly important for visually similar dogs from
different generations, per the interview -- today the classifier has no way to know that "Fibs"
(2015-2019) can't be the dog in a 2023 photo, no matter how similar the embedding looks.

This is the most novel piece of the v1.4 spec -- unlike DT-1111/1112/1113, which are mostly
plumbing existing data through new surfaces, this ticket adds a new signal to the classification
policy and a new piece of owner-editable data. Sequenced after the others (Medium, not High
priority) so the library exists first to make the new "date-conflict" reason visible and useful.

## **Context**

- `Asset.captured_at` (models.py:169) is the capture-date source, already available (see DT-1111).
- `IdentityClassifier.classify()` (`src/immich_dog_tagger/classifier.py:44`) has no notion of the
  crop's own capture date -- it ranks candidates purely by embedding similarity
  (`_cosine_similarity`, line 119). `_load_examples()` (line 127) already loads each
  `EmbeddingExample.identity` via `contains_eager` (line 145), so an identity's date-range fields
  (once added) are available at scoring time with no extra query.
- `Identity` (models.py:38) has no date-range fields today. Its species field (`species`, added by
  DT-1110) is the most recent precedent for adding a new identity-level attribute via an additive
  migration -- same pattern to follow here (`_ensure_*` function in `database.py`, called from
  `create_database()`).
- `ReviewQueryService._review_reason()` (review_query.py:329) already classifies *why* an item
  needs review into `unknown` / `low-confidence` / `candidate-conflict` / `review`, read by the UI
  to explain a prediction. A `date-conflict` reason slots into the same mechanism.
- `policy.py`'s `ClassifierPolicy`/`ClassificationDecision` (DT-1004) is this project's single
  source of truth for classification-decision logic -- any new decision-affecting behavior belongs
  there, not scattered into the classifier or review layer independently.

## **Implementation notes**

### Data model

- Add `active_from: datetime | None` and `active_until: datetime | None` to `Identity`
  (models.py), both nullable, via an additive migration (`_ensure_identity_active_range_columns`
  in `database.py`, following `_ensure_identity_species_column`'s pattern -- a plain
  `ALTER TABLE ... ADD COLUMN`, since unlike DT-1110's uniqueness-constraint change this doesn't
  require a table rebuild).
- Frontend: add optional date-range inputs to `DogManagementCard.tsx`'s per-identity row (next to
  the existing species badge and rename control) and to `DogService.create_dog`/`rename_dog` or a
  new `update_dog` method, whichever fits without overloading rename's existing contract -- a
  dedicated `set_active_range(dog_id, active_from, active_until)` method on `DogService` keeps
  rename's contract (name only) unchanged and is more explicit than folding date fields into it.

### Classification signal

- `IdentityClassifier.classify()` gains an optional `captured_at: datetime | None` parameter (the
  crop being classified, not an example's date). When scoring each candidate
  (`classifier.py:74-78`), check whether `captured_at` falls within
  `[example.identity.active_from, example.identity.active_until]` (either bound absent means
  unbounded on that side; `captured_at` absent, or *both* bounds absent, means "no date signal
  available" -- never penalize). Add a `date_conflict: bool` field to `ClassificationCandidate`
  (not a similarity-score adjustment -- keep the raw embedding similarity meaningful and
  untouched, matching this project's existing stance that similarity is not a calibrated
  probability to be fudged; see v1.0.0.md section 8).
- Every caller that constructs an `IdentityClassifier`/calls `.classify()` needs the crop's
  `captured_at` threaded through: `ClassificationService` (`services/classification.py`) and
  `ReclassifyService` (`services/reclassify.py`), both of which already have access to
  `crop.detection.asset.captured_at` the same way `correction.py` does today.
- `CropClassification.candidates` (JSON) already stores each candidate's `identity`/`similarity`/
  `matched_example_id` (review_query.py:269-278) -- add `date_conflict` to that same JSON shape so
  it survives round-tripping through storage without a new column.
- `ReviewQueryService._review_reason()`: if the top candidate (or the accepted identity) has
  `date_conflict=True`, return `"date-conflict"` as a new reason, checked before falling through to
  the existing `candidate-conflict`/`low-confidence` checks. Add the reason to whatever the
  frontend's reason-badge/copy switch is (wherever `"unknown"`/`"low-confidence"`/
  `"candidate-conflict"` are currently mapped to display text).

### Non-negotiable failure-open behavior

- A crop with no `captured_at` (no EXIF/Immich date): `date_conflict` is always `False` for every
  candidate. Never treat "we don't know the date" as itself suspicious.
- A candidate identity with neither `active_from` nor `active_until` set: `date_conflict` is
  always `False`. Never penalize identities the owner hasn't given date information for --
  existing dog-only projects migrating in (DT-1110's backward-compatibility bar applies equally
  here) must see zero behavior change until the owner opts in by setting a range.

## **Acceptance criteria**

- Two identities with overlapping-looking embeddings but non-overlapping active date ranges are
  distinguishable: a photo captured outside identity A's range but matching A's embedding closely
  is flagged as `date-conflict` rather than silently accepted as A.
- A crop with no capture date, or a candidate identity with no active range set, is scored
  identically to how it would be scored before this ticket -- verified by a regression test, not
  just by reasoning about the code.
- The review/library UI surfaces the `date-conflict` reason distinctly from the existing three
  reasons, so the owner understands *why* a match looks wrong.
- Existing dog-only projects with no identity date ranges set see zero change in classification
  output after this ships (migration is purely additive and opt-in).
- Reclassify's existing idempotency guarantee (re-running with no new reviews produces 0 changed
  predictions) holds with date-aware scoring in place.

## **Testing requirements**

- `tests/test_database.py`: migration test for the new `active_from`/`active_until` columns,
  following `test_database_adds_identity_species_column_and_scopes_uniqueness`'s pattern.
- `tests/test_classifier.py`: a fixture with two identities sharing a near-identical embedding but
  non-overlapping date ranges (mirroring `test_classifier_never_returns_cross_species_candidate`'s
  structure from DT-1110), asserting the out-of-range candidate is flagged; plus explicit tests for
  the two fail-open cases (no crop date; no identity range set).
- `tests/test_dogs_service.py`: test the new `set_active_range` method (or wherever the date
  fields are set) including validation that `active_from` isn't silently accepted after
  `active_until` without at least a sanity check (open question: hard-reject vs. warn -- see spec).
- `tests/test_reclassify.py`: extend the idempotency test to include identities with active
  ranges set, confirming a second run with no new reviews still produces 0 changed predictions.
- `tests/test_review.py`: assert `_review_reason()` returns `"date-conflict"` for a flagged item.

## **Dependencies**

DT-1111 (photo capture date) for the `captured_at` plumbing this ticket's classifier integration
reuses. Does not depend on DT-1112/DT-1113, though surfacing `date-conflict` is more useful once
the library (DT-1112) exists as a place to browse and act on flagged items outside the queue.

## **Suggested commit message**

`feat(DT-1114): flag classifications outside an identity's known active date range`
