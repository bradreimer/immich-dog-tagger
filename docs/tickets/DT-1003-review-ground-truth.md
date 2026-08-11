# TICKET 03: Harden review-to-example persistence

## Status
Completed

## Implementation notes
- Traced both review-to-example paths: `ClassificationCorrectionService.correct()` (single-item review) and `ReviewImporter.import_confirmed()` -> `Learner.learn()` (bulk offline review import). Both ultimately go through `Learner`, so the fix lives there.
- Found a real leakage defect: re-reviewing a crop under a *different* identity (e.g. "Fibs" -> "Hermann") left the stale example under the old identity in place, since `learn_image`/`learn` only deduped by `(identity, crop_path)`, not by `crop_path` alone. A physical crop can only depict one dog.
- `Learner.learn_image()` and `Learner.learn()` now call a shared `_forget_other_identities()` step that deletes any existing example for the same `crop_path` under a *different* identity before upserting, closing the leak while keeping the existing upsert-by-`(identity, crop_path)` dedup for same-identity re-review (already correct, already tested).
- Added `Learner.forget_image()` for the "corrected to Unknown" case: previously the correction path silently skipped the learner entirely when identity was `None`/`"Unknown"`, leaving a stale example behind forever. `ClassificationCorrectionService.correct()` now calls it in that branch.
- Regression tests added at both layers: `tests/test_learner.py` (supersede-on-relearn, forget_image) and `tests/test_correction.py` (re-review under a new identity, correct-to-Unknown), reproducing the exact "50-100 reviewed images -> expected labeled-example population" scenario from the acceptance criteria.

## Goal
Ensure review decisions become reliable classifier examples without duplication or leakage.

## Steps
1. Trace every review path in the UI/backend.
2. Ensure accepted/corrected labels persist as authoritative ground truth.
3. Ensure the associated embedding is available and valid.
4. Upsert rather than duplicate the same logical example.
5. Keep prediction records separate from reviewed labels.
6. Add tests for correction, re-review, and duplicate submission.

## Done when
50-100 reviewed images reliably produce the expected labeled-example population and reclassification cannot overwrite those reviewed labels.
