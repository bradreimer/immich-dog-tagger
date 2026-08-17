# Species Correction

## Purpose
YOLO detection occasionally misidentifies the species of a detected animal -- a cat gets
detected (and cropped) as a dog, or vice versa. Today there is no way to fix this from the
review UI: `Crop.species` is set once at crop-creation time from the detector's raw label and
never changes, so a misdetected crop stays permanently miscategorized -- compared against the
wrong species' reference examples, filed under the wrong species in Learning Progress, and
eventually synced into the wrong Immich album.

## User Story
As a reviewer, I want to explicitly mark a review item as "Dog" or "Cat" when the detector got
the species wrong, so the item gets compared against the correct species' identities and synced
to the correct album, without having to give up and skip it.

## Goals
- A reviewer can correct a review item's species directly from the Review page.
- The correction takes effect immediately: the crop is rescored against the corrected species'
  reference examples using its existing embedding (no re-download or re-embedding needed), and
  the identity chooser switches to that species' identities.
- The two species actions are visually distinguishable from each other and from the identity
  buttons, using existing design-system colors (not novel colors invented for this feature).
- Per-species Learning Progress metrics reflect the corrected species, not the detector's
  original (possibly wrong) label.

## Non-goals
- Changing the YOLO model, detection thresholds, or crop generation.
- A generalized/arbitrary species list -- still hardcoded to `dog`/`cat` (see DT-1110).
- Bulk/batch species correction across many items at once.
- Retroactively re-running detection; this only corrects the species of an existing crop.

## Requirements
- New endpoint to change a classification's crop species, distinct from identity correction
  (`POST /classifications/{id}/correct`), since a species change does not by itself decide an
  identity -- it's a precondition the reviewer must still confirm/pick an identity after.
- Changing species must not mark the item as "reviewed": no `ReviewAction` row is written by the
  species correction itself, since the item still needs a human identity decision afterward (or
  the item would silently vanish from the active review queue while still effectively
  unclassified -- see `ReviewQueryService.review_queue_count()`).
- Switching species re-scores the crop's existing stored embedding against the new species'
  reference pool (reusing `IdentityClassifier`), producing a fresh best-guess identity/confidence/
  candidates rather than always resetting to Unknown.
- Any prior learning example for this crop's path is forgotten (`Learner.forget_image`), since it
  was filed under the wrong species' identity.
- A no-op (correcting to the species the crop already has) must not reprocess anything.
- Review page shows two distinctly colored buttons, "Dog" and "Cat", each carrying an icon and
  text label (not color alone -- see ux-principles.md #13).
- `services/metrics.py`'s per-species breakdown must key off `Crop.species` (the corrected,
  authoritative value), not `Detection.label` (the detector's original, possibly-wrong output) --
  today these always match since nothing could diverge them; this feature makes them divergeable.

## Acceptance Criteria
- Clicking "Cat" on a dog-detected review item changes `crop.species` to `cat`, recomputes
  identity/confidence/candidates against cat reference examples, and the identity chooser now
  shows cat identities.
- The item remains in the active review queue after a species correction (assuming it's still
  unknown or below threshold), rather than disappearing as if reviewed.
- Clicking the species the item already has is a no-op.
- Confirming an identity afterward records a normal `ReviewAction` (`CORRECT`) exactly as it does
  today.
- `GET /metrics`'s per-species breakdown counts a species-corrected crop under its corrected
  species.
- Existing dog-only and mixed dog/cat review/classification/sync behavior is unchanged.

## Open Questions
- Should a species correction also flag the underlying `Detection.label` as suspect anywhere
  (e.g. for future detector quality analysis)? Out of scope for now -- `Detection.label` remains
  the detector's raw, historical output; `Crop.species` is the corrected, authoritative value.
