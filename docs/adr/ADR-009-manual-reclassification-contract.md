# ADR-009: Manual reclassification exposes date, species, identity, and decline-to-label together

## Status

Accepted.

## Context

A human overriding the classifier for one photo -- from the active review queue, or from the
Library's per-photo "Edit" link (`/review?classification_id=...`, both routed through the same
`ReviewCard` component per [ADR-008](ADR-008-library-flat-browse-workspace.md)) -- has accreted
four distinct pieces of capability across separate releases, each shipped to fix its own issue
without ever being written down together as what "manually reclassify a photo" is required to
offer:

- The photo's own capture date, shown beside the prediction so a reviewer can weigh a match against
  when it was taken (`PredictionCard`).
- Species correction, dog &harr; cat (`SpeciesChooser`, added with cat support).
- Identity selection, scoped to the (possibly just-corrected) species (`IdentityChooser`).
- A "not a dog or cat" toggle (`NotAnimalToggle`; issue #185, corrected by #186; see
  [docs/specs/photo-lookup.md](../specs/photo-lookup.md)'s "not a dog or cat" addendum).

The fourth item's own documentation (`false_positives.py`'s module docstring, the Photo Lookup
spec addendum, `NotAnimalToggle`'s original comment) describes it narrowly, as a **YOLO false
positive**: "isn't a dog or cat at all -- a stuffed animal, a shadow, a person." In practice a
reviewer reaches for the same button for a second, distinct situation the narrow description
doesn't name: there genuinely is a dog or cat in the crop, but the reviewer doesn't recognize it,
or doesn't want to assign it a label right now (a stray, a background pet not one of the household's
own, a photo too ambiguous to commit to). Both situations already resolve identically today:
`FalsePositiveService.mark()` settles the classification to Unknown (`identity=None`) through the
same `ClassificationCorrectionService.correct()` every other correction uses, and separately flips
`Crop.not_animal` purely so the UI can render that the crop was explicitly marked (dimmed/dashed
box in Photo Lookup, a `not_animal` badge in Library/Review) rather than merely left unclassified.
Nothing downstream reads `not_animal` to mean "definitely zero animals here" -- sync, the review
queue, Insights occurrence tracking, and the learner all just see "settled, no identity," the same
state a reviewer reaches by leaving a photo at Unknown without touching the toggle at all.

## Decision

Manual reclassification of a single photo -- today `ReviewCard` and everything that renders it --
is required, as one contract, to always expose all four of:

1. **The photo's capture date.**
2. **Species correction** (dog &harr; cat).
3. **Identity selection**, scoped to the current (possibly corrected) species.
4. **A "not a dog or cat" toggle**, understood to cover two legitimate, equally valid reasons a
   reviewer reaches for it:
   - (a) literal YOLO false positive -- there is no dog or cat in the crop at all, or
   - (b) there is a dog or cat, but the reviewer doesn't recognize it or doesn't want to assign it
     an identity right now.

   Both are the same state transition (settle to Unknown, flag the crop) and are not distinguished
   by any new field, enum, or table -- the flag stays the single boolean it already is.

Any future manual-reclassification surface (a new page, a bulk-correct flow, a keyboard-only quick
editor) must offer all four, not a subset. A widget that, say, only offers identity selection
without a way to also flag "not a dog or cat" would not satisfy this contract.

## Alternatives considered

- **Add a second, separate control for "recognized but unlabeled/declined"**, distinct from
  "not a dog or cat" (e.g. a new `Crop.unlabeled_reason` enum). Rejected: it would duplicate
  `not_animal`'s existing settle-to-Unknown behavior for zero behavioral difference on the backend
  -- more UI surface and a new field to migrate and maintain, to distinguish two cases nothing
  downstream currently needs to tell apart. If a real need to distinguish them shows up (e.g. a
  "detector accuracy" metric that must exclude case (b)), that's a new, separately-scoped decision,
  not a reason to speculatively add the field now.
- **Leave "not a dog or cat" documented strictly as "no animal present."** Rejected: this is what
  the code and spec said before this ADR, and it doesn't match how the control needs to be used --
  a reviewer who recognizes an unfamiliar dog has no other way to settle that photo out of the
  active queue today besides this toggle (leaving it at Unknown without touching the toggle also
  works, but doesn't record that a human looked at it, so it isn't equivalent from a review-progress
  standpoint). Leaving the narrower description in place risks a future contributor "fixing" the
  toggle to reject use case (b), breaking a workflow reviewers already depend on.

## Consequences

- No schema or backend behavior changes as a result of this decision alone -- `Crop.not_animal` and
  `ClassificationCorrectionService.correct(id, None)` already implement it correctly; this ADR
  documents the semantics that were already true and makes the dual meaning explicit going forward.
- `NotAnimalToggle.tsx`'s comment and `false_positives.py`'s module docstring are updated alongside
  this ADR to state the dual meaning, so their "isn't a dog or cat at all" framing no longer
  contradicts how the control is actually used.
- If a future feature needs to tell "true false positive" apart from "recognized but declined"
  (for example, a YOLO precision metric), that feature must introduce its own way to distinguish
  them -- this ADR deliberately does not attempt to infer or backfill that distinction from
  historical `not_animal` marks, since today's single flag carries no information about which of
  the two reasons a reviewer had in mind.
