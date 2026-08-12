# DT-1004: Centralize nearest-neighbor decision policy

## **ID**

DT-1004

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-5, responsible architectural guideline #7

## **Priority**

High

## **Status**

Completed

## **Goal**

Make classification behavior explicit, deterministic, and testable.

## **Context**

The nearest-neighbor confidence threshold (0.80) and candidate-list size were duplicated as literals across five modules (`classifier.py`, `services/classification.py`, `services/review_query.py`, `cli.py`, the review API route), with no persisted record of which configuration produced a given prediction. Centralizing this was a prerequisite for Reclassify (DT-1001) to be able to record and later detect policy drift between passes.

## **Implementation notes**

- Added `src/immich_dog_tagger/policy.py`: `ClassifierPolicy` (version, confident_threshold, candidate_limit) and `ClassificationDecision` (CONFIDENT/NEEDS_REVIEW/UNKNOWN), with a `DEFAULT_POLICY` singleton.
- `IdentityClassifier`, `ClassificationService`, and `ReviewQueryService` now take a `policy` and resolve their threshold/candidate-limit defaults from it instead of hardcoded `0.80`/`3` literals.
- `ReviewQueryService._review_reason` now derives "unknown"/"low-confidence" from `policy.decide()` instead of a second hardcoded threshold.
- CLI (`classify`, `active-review`) and the `/review` API route default to `DEFAULT_POLICY.confident_threshold` rather than a duplicated literal.
- Added `CropClassification.classifier_version` (persists which policy version produced an AUTO prediction) plus an additive migration in `database.py`.

## **Acceptance criteria**

- The UI does not implement ML policy.
- The same policy is used consistently by pipeline classification and Reclassify.
- Confident, needs-review, and unknown states are explicit and testable in isolation.
- The classifier configuration is persisted alongside each prediction.

## **Testing requirements**

`tests/test_policy.py` (boundary-case decision tests), plus migration coverage in `tests/test_database.py`.

## **Dependencies**

DT-1000.

## **Suggested commit message**

`feat(DT-1004): centralize nearest-neighbor classifier policy`
