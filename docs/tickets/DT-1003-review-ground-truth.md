# DT-1003: Harden review-to-example persistence

## **ID**

DT-1003

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-3, responsible architectural guideline #2

## **Priority**

High

## **Status**

Completed

## **Goal**

Ensure review decisions become reliable classifier examples without duplication or leakage.

## **Context**

Human review corrections are the system's ground truth and the sole source of new training examples in v1.0.0 (there is no separate training step). A defect here silently degrades every future classification, so this ticket audits and hardens every path from a review action to a persisted `EmbeddingExample`.

## **Implementation notes**

- Traced both review-to-example paths: `ClassificationCorrectionService.correct()` (single-item review) and `ReviewImporter.import_confirmed()` -> `Learner.learn()` (bulk offline review import). Both ultimately go through `Learner`, so the fix lives there.
- Found a real leakage defect: re-reviewing a crop under a *different* identity (e.g. "Fibs" -> "Hermann") left the stale example under the old identity in place, since `learn_image`/`learn` only deduped by `(identity, crop_path)`, not by `crop_path` alone. A physical crop can only depict one dog.
- `Learner.learn_image()` and `Learner.learn()` now call a shared `_forget_other_identities()` step that deletes any existing example for the same `crop_path` under a *different* identity before upserting, closing the leak while keeping the existing upsert-by-`(identity, crop_path)` dedup for same-identity re-review (already correct, already tested).
- Added `Learner.forget_image()` for the "corrected to Unknown" case: previously the correction path silently skipped the learner entirely when identity was `None`/`"Unknown"`, leaving a stale example behind forever. `ClassificationCorrectionService.correct()` now calls it in that branch.

## **Acceptance criteria**

- 50-100 reviewed images reliably produce the expected labeled-example population.
- Re-reviewing an item under a different identity does not leave a stale example under the old identity.
- Correcting a crop to Unknown removes any example it previously contributed.
- Reclassification cannot overwrite reviewed labels (verified in DT-1001/DT-1009).

## **Testing requirements**

`tests/test_learner.py` (supersede-on-relearn, `forget_image`) and `tests/test_correction.py` (re-review under a new identity, correct-to-Unknown), reproducing the exact "50-100 reviewed images -> expected labeled-example population" scenario from the acceptance criteria.

## **Dependencies**

DT-1000.

## **Suggested commit message**

`fix(DT-1003): close review-to-example leakage on re-review`
